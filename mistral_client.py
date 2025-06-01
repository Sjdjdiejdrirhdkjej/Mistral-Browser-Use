import requests
import json
import base64
import os

class MistralClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.base_url = "https://api.mistral.ai/v1"
        
        if not self.api_key:
            raise ValueError("Mistral API key is required")
    
    def analyze_and_decide(self, image_base64, user_objective, model_name: str, current_context=None, system_prompt_override: str | None = None):
        """Analyze screenshot and decide on next action"""

        # 1. Input Validation
        if not image_base64:
            error_msg = "Validation Error: image_base64 provided to analyze_and_decide is empty or None."
            print(error_msg)
            return {"thinking": error_msg, "action": "ERROR_VALIDATION"}
        
        # Construct the prompt for analysis (remains the same)
        default_system_prompt = """You are an expert web automation assistant. Your task is to analyze the provided screenshot of a webpage and the current user objective, then decide the single next best action to take.

AVAILABLE ACTIONS:
- click(INDEX): Click on an element identified by its red numerical label (INDEX) in the screenshot.
- type("TEXT_TO_TYPE", into="ELEMENT_DESCRIPTOR"): Type the specified TEXT_TO_TYPE into an input field. ELEMENT_DESCRIPTOR should be a concise description of the target input field, e.g., "username input", "search box with current value 'example'", "text field labeled 'Password'".
- press_key("KEY_NAME"): Simulate pressing a special key. KEY_NAME must be one of: "enter", "escape", "tab". Use "enter" for submitting forms or search queries, "escape" for closing modals/dialogs, "tab" for navigating form elements.
- navigate_to("URL_STRING"): Go to a specific web address. The URL_STRING should be the full address (e.g., "https://www.example.com").
- COMPLETE: Use this action if the current user objective appears to be fully achieved based on the screenshot.

YOUR RESPONSE MUST BE A VALID JSON OBJECT. IT MUST STRICTLY ADHERE TO THE FOLLOWING STRUCTURE AND FIELDS:
{
    "thinking": "Your detailed step-by-step reasoning. Explain what you observe in the screenshot, how it relates to the current objective and overall goal, and why you are choosing the specific action. If you are unsure, explain the ambiguity. This field is mandatory.",
    "action": "The chosen action string (e.g., click(5), type('hello world', into='search input'), press_key('enter'), COMPLETE). This field is mandatory."
}

GUIDELINES:
1.  Carefully examine all numbered elements in the screenshot.
2.  Relate the visual information to the current task/objective (`user_objective`) and the overall goal (`current_context`).
3.  Choose the most logical and direct next action to progress towards the objective.
4.  Be precise. For `click`, use the correct INDEX. For `type`, clearly describe the target input field based on visible text, labels, or current values.
5.  If the objective is met, use `COMPLETE`.
6.  If the page shows an error or is not what's expected (e.g., a 404 page, unexpected login screen), your thinking should reflect this and you should still choose the best possible action (which might be `COMPLETE` if the objective cannot be progressed).
7.  Ensure your `ELEMENT_DESCRIPTOR` for typing is based on visible text, labels, or current values to help locate the element.
"""

        user_prompt_text = f"""Current Task/Objective: {user_objective}
Overall Goal: {current_context if current_context else "Not specified, focus on the current task."}

Analyze the provided screenshot and determine the single next action to take. Use the available actions and follow the response format strictly."""

        response = None # Initialize response here to ensure it's in scope for the final except block

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt_override if system_prompt_override else default_system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt_text
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # 3. Inside the Main try Block
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}. Response text: {response.text}"
                print(error_msg)
                raise Exception(error_msg) # Will be caught by the generic except Exception
            
            result = response.json() # This can raise json.JSONDecodeError, caught by specific handler below

            if not (
                isinstance(result, dict) and
                'choices' in result and
                isinstance(result['choices'], list) and
                len(result['choices']) > 0 and
                isinstance(result['choices'][0], dict) and
                'message' in result['choices'][0] and
                isinstance(result['choices'][0]['message'], dict) and
                'content' in result['choices'][0]['message']
            ):
                error_msg = f"API response structure was unexpected. Full response: {result}"
                print(error_msg)
                raise Exception(error_msg) # Will be caught by the generic except Exception

            content = result['choices'][0]['message']['content']
            
            if not content: # Check for None or empty string
                error_msg = "AI response content was empty or None."
                print(error_msg)
                return {"thinking": error_msg, "action": "ERROR_EMPTY_CONTENT"}

            # 4. Inner try...except Block (for parsing content)
            try:
                parsed_response = json.loads(content)
                if not (isinstance(parsed_response, dict) and \
                   'thinking' in parsed_response and \
                   'action' in parsed_response):
                    error_message = f"AI response content is valid JSON but not the expected dict structure or missing keys. Parsed content: {parsed_response}"
                    print(error_message)
                    return {
                        "thinking": error_message,
                        "action": "ERROR_INVALID_RESPONSE_STRUCTURE"
                    }
                return parsed_response # Success path
            except json.JSONDecodeError as jde:
                error_msg = f"JSONDecodeError: Failed to parse AI's 'content' string. Content: '{content}'. Error: {str(jde)}"
                print(error_msg)
                return {"thinking": error_msg, "action": "ERROR_CONTENT_NOT_JSON"}

        # 5. Outer except Blocks
        except requests.exceptions.Timeout as te:
            error_message = f"API request timed out for model {model_name}. Error: {str(te)}"
            print(error_message)
            return {"thinking": error_message, "action": "ERROR_TIMEOUT"}
        except json.JSONDecodeError as jde_outer: # Catches response.json() failure
            response_text_info = "N/A"
            if response is not None and hasattr(response, 'text'):
                response_text_info = response.text
            error_message = f"Failed to parse the main API response (e.g., from response.json()). Response text: '{response_text_info}'. Error: {str(jde_outer)}"
            print(error_message)
            return {"thinking": error_message, "action": "ERROR_API_RESPONSE_NOT_JSON"}
        except Exception as e: # Catch-all for the main try block
            response_text_info = "N/A"
            if response is not None and hasattr(response, 'text'): # Check if response object exists and has text
                response_text_info = response.text
            error_message = f"An unexpected error occurred in analyze_and_decide (model: {model_name}): {str(e)}. Response text: {response_text_info}"
            print(error_message)
            return {"thinking": error_message, "action": "ERROR_UNEXPECTED"}
    
    def test_connection(self):
        """Test the API connection"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Simple test request
            payload = {
                "model": "mistral-small-latest",
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello, this is a test."
                    }
                ],
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception:
            return False

    def generate_steps_for_todo(self, user_prompt: str, model_name: str, system_prompt_override: str | None = None) -> list[str]:
        """
        Generates a list of actionable steps for web automation based on a user prompt.

        Args:
            user_prompt: The high-level objective from the user.
            model_name: The Mistral model to use for generation.

        Returns:
            A list of strings, where each string is a step. Returns an empty list if parsing fails.
        """
        default_system_prompt = """You are an expert planning agent. Your primary function is to break down a user's high-level web automation objective into a detailed, ordered list of specific sub-tasks. These sub-tasks will be executed by an automation tool.

GUIDELINES:
1.  Analyze the user's objective carefully.
2.  Generate a sequence of actionable steps. Each step should be a concrete action (e.g., "Navigate to URL", "Click the 'Login' button", "Type 'search query' into the search bar", "Verify that the text 'Welcome User' is visible") or a verification point.
3.  For moderately complex objectives, aim for 10-15 granular steps. For very complex objectives, more steps may be necessary. For simple objectives, fewer steps are fine.
4.  The steps should be logical and follow a sequence that a human would perform to achieve the objective.
5.  Each step must be a clear, concise instruction.
6.  Consider edge cases or common issues if applicable (e.g., "Check for login errors before proceeding"). This is optional but helpful.

OUTPUT FORMAT:
Present the steps as a simple list of strings, with each step on a new line. Each step should start with '- ' (a hyphen followed by a space).

Example for objective "Log into the website example.com and go to the dashboard":
- Navigate to https://example.com
- Click the 'Login' link or button.
- Type 'testuser' into the username field.
- Type 'password123' into the password field.
- Click the 'Submit' or 'Login' button.
- Verify that the page shows 'Welcome testuser' or similar.
- Click on the 'Dashboard' link in the navigation menu.
- Verify that the dashboard page is loaded by checking for 'User Dashboard' title.
"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt_override if system_prompt_override else default_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2, # Lower temperature for more deterministic, list-like output
                "max_tokens": 1500
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=45  # Increased timeout for potentially longer generation
            )

            if response.status_code != 200:
                # Consider logging the error response.text for debugging
                print(f"API request failed for step generation: {response.status_code} - {response.text}")
                return []

            result = response.json()

            if not result.get('choices') or not result['choices'][0].get('message') or not result['choices'][0]['message'].get('content'):
                print("Unexpected API response structure for step generation.")
                return []

            content = result['choices'][0]['message']['content']

            # Parse the model's response to extract steps
            steps = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Remove common list prefixes like "-", "*", or "1. "
                if line.startswith("- "):
                    steps.append(line[2:].strip())
                elif line.startswith("* "):
                    steps.append(line[2:].strip())
                elif line.startswith("1. ") and len(line) > 3: # Check length to avoid "1." as a step
                     steps.append(line[3:].strip())
                elif line[0].isdigit() and line[1] == '.' and line[2] == ' ':
                    steps.append(line[3:].strip())
                else:
                    steps.append(line) # Add as is if no common prefix

            return steps

        except requests.exceptions.Timeout:
            print("API request timed out during step generation.")
            return []
        except Exception as e:
            print(f"Failed to generate steps: {str(e)}")
            return []

    def analyze_state_vision(self, image_base64: str, current_task: str, objective: str, model_name: str) -> dict:
        """
        Analyzes a screenshot (image_base64) in the context of the current_task and overall_objective
        using the specified vision model.

        Args:
            image_base64: Base64 encoded string of the PNG image.
            current_task: The current task being attempted.
            objective: The overall user objective.
            model_name: The Mistral model to use for analysis (e.g., "pixtral-large-latest").

        Returns:
            A dictionary with "error", "task_completed", "objective_completed", and "summary".
            Returns a default error dictionary if parsing fails.
        """
        system_prompt = """You are an expert web page analysis agent. Your role is to meticulously analyze a provided screenshot of a web page in the context of a current task and an overall objective.

Your response MUST be a JSON object with the following structure and data types:
{
    "error": "string_or_null",    // If an error message is visible (e.g., 'Login failed', '404 Not Found') or the page is clearly unexpected (e.g., a login page when already logged in), describe the error. Otherwise, this MUST be null.
    "task_completed": boolean,    // Based on the screenshot and the 'Current Task', is this specific task now complete? This MUST be true or false.
    "objective_completed": boolean, // Considering the screenshot and the 'Overall Objective', does it appear the entire objective has been achieved? This MUST be true or false.
    "summary": "string"           // A concise textual summary of the current page state as it relates to the task and objective. Describe what you see that is relevant.
}

GUIDELINES:
1.  Examine the screenshot thoroughly for any visual cues related to errors, task progression, or objective achievement.
2.  Pay close attention to the wording of the 'Current Task' and 'Overall Objective' provided by the user. These will be included in the user message.
3.  `task_completed` refers to the *specific* task provided, not the overall objective.
4.  `objective_completed` refers to the *entire* multi-step objective.
5.  If you are unsure about a boolean field, err on the side of `false` and explain your reasoning in the `summary`.
6.  The `summary` should be brief but informative, justifying your boolean decisions.
7.  Strictly adhere to the JSON format. Ensure `task_completed` and `objective_completed` are actual boolean values (true/false), not strings. `error` must be a string or null.
"""

        user_message_text = f"""CONTEXT FOR ANALYSIS:
Current Task: "{current_task}"
Overall Objective: "{objective}"

Please analyze the provided screenshot based on the system instructions and the context above.
Provide your analysis STRICTLY in the specified JSON format.
"""

        user_content = [
            {
                "type": "text",
                "text": user_message_text
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            }
        ]

        default_error_response = {
            "error": "Failed to parse analysis from model or API error.",
            "task_completed": False,
            "objective_completed": False,
            "summary": "Could not obtain analysis due to an error."
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.1, # Low temperature for consistent JSON output
                "max_tokens": 1000,
                "response_format": {"type": "json_object"} # Request JSON output
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                print(f"API request failed for vision analysis: {response.status_code} - {response.text}")
                # Try to get more details from response if possible
                try:
                    error_details = response.json()
                    default_error_response["error"] = f"API Error: {response.status_code} - {error_details.get('message', response.text)}"
                except json.JSONDecodeError:
                     default_error_response["error"] = f"API Error: {response.status_code} - {response.text}"
                return default_error_response

            result_text = response.json()['choices'][0]['message']['content']

            # The response should be a JSON string, parse it
            parsed_json = json.loads(result_text)

            # Validate the structure of the parsed JSON
            if not all(key in parsed_json for key in ["error", "task_completed", "objective_completed", "summary"]):
                print(f"Model response missing required JSON keys. Response: {result_text}")
                # Try to salvage what we can, or return a more specific error
                salvaged_response = {
                    "error": parsed_json.get("error", "Model response missing 'error' key."),
                    "task_completed": parsed_json.get("task_completed", False),
                    "objective_completed": parsed_json.get("objective_completed", False),
                    "summary": parsed_json.get("summary", "Model response incomplete.")
                }
                # Ensure boolean types for completion flags
                if not isinstance(salvaged_response["task_completed"], bool):
                    salvaged_response["task_completed"] = False
                if not isinstance(salvaged_response["objective_completed"], bool):
                    salvaged_response["objective_completed"] = False
                return salvaged_response

            # Ensure boolean types for completion flags, as models might return strings like "true"
            parsed_json["task_completed"] = str(parsed_json.get("task_completed", "false")).lower() == "true"
            parsed_json["objective_completed"] = str(parsed_json.get("objective_completed", "false")).lower() == "true"


            return parsed_json

        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON response from model: {e}. Response text: {result_text if 'result_text' in locals() else 'N/A'}")
            default_error_response["error"] = f"Failed to decode JSON: {e}"
            return default_error_response
        except requests.exceptions.Timeout:
            print("API request timed out during vision analysis.")
            default_error_response["error"] = "API request timed out."
            return default_error_response
        except Exception as e:
            print(f"Failed to analyze state with vision: {str(e)}")
            default_error_response["error"] = f"Generic error in vision analysis: {str(e)}"
            return default_error_response