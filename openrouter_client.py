import openai # Using the openai SDK
import os
import json
import base64
import re

class OpenRouterClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key is required. Set it as an environment variable OPENROUTER_API_KEY or pass it to the constructor.")
        try:
            self.client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1", # Crucial for OpenRouter
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": os.getenv("OPENROUTER_REFERRER_URL", "http://localhost:8501"), # Allow override by env var
                    "X-Title": os.getenv("OPENROUTER_X_TITLE", "Web Automation Assistant"),  # Allow override by env var
                }
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenRouter client: {e}")
        self.default_text_model = "mistralai/mistral-7b-instruct"
        self.default_vision_model = "openai/gpt-4o" # Example, user should ensure this model is available/suitable on OR

    def generate_steps_for_todo(self, user_prompt: str, model_name: str) -> list[str]:
        if not model_name:
            model_name = self.default_text_model
            print(f"Warning: No model_name provided for OpenRouter step generation, using default: {model_name}")

        system_prompt = """You are an expert planning agent. Your task is to break down a user's objective into a series of simple, actionable steps. Each step should be a concise instruction.

Output Format:
Respond with a list of steps, each on a new line, prefixed with "- ".

Example:
User Objective: Book a flight from London to New York for next week.
- Search for flights from London to New York for next week.
- Compare flight options based on price and schedule.
- Select the preferred flight.
- Enter passenger details.
- Complete the booking and payment.

Ensure your output strictly follows this format. Do not include any other explanatory text, preamble, or summarization.
"""
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,
                temperature=0.2
            )
            content = response.choices[0].message.content
            steps = []
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    steps.append(line[2:].strip())
                elif line:
                    steps.append(line)
            return steps
        except Exception as e:
            print(f"Error generating steps with OpenRouter (model: {model_name}): {e}")
            return []

    def analyze_state_vision(self, image_base64: str, current_task: str, objective: str, model_name: str) -> dict:
        if not model_name:
            model_name = self.default_vision_model
            print(f"Warning: No model_name provided for OpenRouter vision analysis, using default: {model_name}")

        system_prompt = """You are an expert web page analysis agent. You will be provided with a screenshot of a web page, the current task, and the overall user objective.
Your goal is to analyze the visual information in the screenshot to determine if the current task has been completed, if the overall objective has been met, or if there's any error visible.

You MUST respond with a JSON object containing the following keys:
- "error": A string describing any error condition observed on the page (e.g., "Login failed", "Product not found"). If no error, this should be null.
- "task_completed": A boolean (true/false) indicating if the current specific task appears to be completed based on the screenshot.
- "objective_completed": A boolean (true/false) indicating if the overall user objective appears to be achieved based on the screenshot.
- "summary": A brief textual summary of your visual analysis and reasoning.

Ensure your output is ONLY the JSON object.
"""

        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}", "detail": "auto"}
            },
            {
                "type": "text",
                "text": f"CONTEXT FOR ANALYSIS:\nCurrent Task: \"{current_task}\"\nOverall Objective: \"{objective}\"\n\nPlease analyze the provided screenshot and provide your analysis STRICTLY in the specified JSON format."
            }
        ]
        default_error_response = {"error": "Failed to analyze state or parse AI response.", "task_completed": False, "objective_completed": False, "summary": "Could not obtain analysis."}
        response_text = "" # Initialize for wider scope in case of exceptions

        try:
            parsed_json = None
            try: # Attempt with JSON mode
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                response_text = response.choices[0].message.content
                parsed_json = json.loads(response_text)
            except Exception as e_json_mode:
                print(f"Info: JSON mode might have failed for {model_name} on OpenRouter ({e_json_mode}). Trying text completion parsing.")
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=1000
                )
                response_text = response.choices[0].message.content
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    parsed_json = json.loads(json_str)
                else:
                    default_error_response["summary"] = "No valid JSON object found in AI response from OpenRouter after fallback."
                    default_error_response["raw_ai_output"] = response_text
                    return default_error_response

            if not parsed_json: # Should not happen if logic above is correct, but as a safeguard
                default_error_response["summary"] = "Internal error: parsed_json is None before validation."
                default_error_response["raw_ai_output"] = response_text
                return default_error_response

            if all(key in parsed_json for key in ["error", "task_completed", "objective_completed", "summary"]):
                parsed_json["task_completed"] = str(parsed_json.get("task_completed", "false")).lower() == "true"
                parsed_json["objective_completed"] = str(parsed_json.get("objective_completed", "false")).lower() == "true"
                error_val = parsed_json.get("error")
                if isinstance(error_val, str) and error_val.lower() in ["null", "none"]:
                    parsed_json["error"] = None
                elif not error_val:
                    parsed_json["error"] = None
                return parsed_json
            else:
                default_error_response["summary"] = "AI response JSON (OpenRouter) missing required keys."
                default_error_response["raw_ai_output"] = response_text
                return default_error_response

        except json.JSONDecodeError as je:
            default_error_response["summary"] = f"Failed to decode JSON from OpenRouter response: {je}"
            default_error_response["raw_ai_output"] = response_text
            return default_error_response
        except Exception as e:
            print(f"Error in analyze_state_vision with OpenRouter (model: {model_name}): {e}")
            default_error_response["error"] = f"API call failed: {str(e)}"
            return default_error_response

    def analyze_and_decide(self, image_base64: str, user_objective: str, model_name: str, current_context: str = None) -> dict:
        if not model_name:
            model_name = self.default_vision_model
            print(f"Warning: No model_name provided for OpenRouter decision, using default: {model_name}")

        system_prompt = """You are an expert web automation assistant. Your task is to analyze the provided screenshot of a web page, along with the user's current objective and overall goal, and decide the single next best action to perform.

AVAILABLE ACTIONS:
1.  `click(INDEX)`: Click on an element identified by its numerical index shown on the screenshot. Example: `click(3)`
2.  `type("TEXT_TO_TYPE", into="DESCRIPTOR")`: Type text into an input field. `DESCRIPTOR` should be a short description of the target field (e.g., "username field", "search bar", "item quantity input with current value 2"). Example: `type("hello world", into="search bar")`
3.  `press_key("KEY_NAME")`: Press a special key. Supported keys: "enter", "escape", "tab". Example: `press_key("enter")`
4.  `navigate_to("URL")`: Navigate to a specific URL. Example: `navigate_to("https://www.example.com")`
5.  `COMPLETE`: If the user's current objective/task seems to be fully achieved based on the screenshot.
6.  `ERROR("REASON")`: If you cannot determine a valid action or encounter an issue. Example: `ERROR("Button not found")`

RESPONSE FORMAT:
You MUST respond with a JSON object containing two keys:
- "thinking": A brief step-by-step thought process explaining your reasoning for the chosen action.
- "action": The chosen action string from the available actions.

Ensure your output is ONLY the JSON object.
"""

        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}", "detail": "auto"}
            },
            {
                "type": "text",
                "text": f"Current Task/Objective: {user_objective}\nOverall Goal: {current_context if current_context else 'Not specified'}\n\nAnalyze the screenshot and determine the next action."
            }
        ]
        default_error_response = {"thinking": "Error: Could not parse AI response or response incomplete.", "action": "ERROR('Malformed response from AI or internal error')"}
        response_text = "" # Initialize for wider scope

        try:
            parsed_json = None
            try: # Attempt with JSON mode
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                response_text = response.choices[0].message.content
                parsed_json = json.loads(response_text)
            except Exception as e_json_mode:
                print(f"Info: JSON mode might have failed for {model_name} on OpenRouter ({e_json_mode}). Trying text completion parsing for decision.")
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=1000
                )
                response_text = response.choices[0].message.content
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    parsed_json = json.loads(json_str)
                else:
                    default_error_response["thinking"] = "No valid JSON object found in AI decision response from OpenRouter after fallback."
                    default_error_response["raw_ai_output"] = response_text
                    return default_error_response

            if not parsed_json: # Safeguard
                default_error_response["thinking"] = "Internal error: parsed_json is None before decision validation."
                default_error_response["raw_ai_output"] = response_text
                return default_error_response

            if all(key in parsed_json for key in ["thinking", "action"]):
                return parsed_json
            else:
                default_error_response["thinking"] = "AI response JSON (OpenRouter) missing required keys (thinking/action)."
                default_error_response["raw_ai_output"] = response_text
                return default_error_response

        except json.JSONDecodeError as je:
            default_error_response["thinking"] = f"Failed to decode JSON from OpenRouter decision response: {je}"
            default_error_response["raw_ai_output"] = response_text
            return default_error_response
        except Exception as e:
            print(f"Error in analyze_and_decide with OpenRouter (model: {model_name}): {e}")
            default_error_response["thinking"] = f"API call failed during decision: {str(e)}"
            return default_error_response

    def test_connection(self):
        try:
            test_model = self.default_text_model # Use the defined default text model
            self.client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "Hello, world from OpenRouter test"}],
                max_tokens=10
            )
            return True
        except openai.APIConnectionError:
            print("OpenRouter APIConnectionError: Could not connect.")
            return False
        except openai.AuthenticationError:
            print("OpenRouter AuthenticationError: API key is invalid or not authorized.")
            return False
        except openai.RateLimitError:
            print("OpenRouter RateLimitError: Rate limit exceeded.")
            return False
        except Exception as e:
            print(f"Failed to connect to OpenRouter: {e}")
            return False
