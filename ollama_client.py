import ollama
import json
import re

class OllamaClient:
    def __init__(self):
        self.model = 'deepseek-r1'
        self.host = 'http://localhost:11434'
        self.client = ollama.Client(host=self.host)

    def test_connection(self):
        """Test the connection to the Ollama server."""
        try:
            self.client.list() # Simple command to check if server is reachable
            return True
        except Exception as e:
            print(f"Failed to connect to Ollama server at {self.host}: {e}")
            return False

    def generate_steps_for_todo(self, user_prompt: str, model_name: str = None) -> list[str]:
        """
        Generates a list of actionable steps for web automation based on a user prompt.
        Args:
            user_prompt: The high-level objective from the user.
            model_name: The Ollama model to use (optional, defaults to client's model).
        Returns:
            A list of strings, where each string is a step. Returns an empty list if parsing fails.
        """
        current_model = model_name if model_name else self.model

        system_prompt = """You are an expert planning agent. Your primary function is to break down a user's high-level web automation objective into a detailed, ordered list of specific sub-tasks. These sub-tasks will be executed by an automation tool.

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
            response = self.client.chat(
                model=current_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ]
            )
            content = response['message']['content']

            # Parse the model's response to extract steps
            steps = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("- "):
                    steps.append(line[2:].strip())
                elif line.startswith("* "):
                    steps.append(line[2:].strip())
                elif line.startswith("1. ") and len(line) > 3:
                     steps.append(line[3:].strip())
                elif line[0].isdigit() and line[1] == '.' and line[2] == ' ':
                    steps.append(line[3:].strip())
                else:
                    steps.append(line)
            return steps

        except Exception as e:
            print(f"Failed to generate steps with Ollama model {current_model}: {e}")
            return []

    def analyze_and_decide(self, user_objective: str, model_name: str = None, current_context: str = None, screen_description: str = None):
        """
        Analyze the current situation (textual description of screen if available)
        and decide on the next action.
        Args:
            user_objective: The current user objective.
            model_name: The Ollama model to use (optional, defaults to client's model).
            current_context: The overall goal or broader context.
            screen_description: A textual description of the current screen or relevant elements.
                               This is used instead of direct image analysis for text-based models.
        Returns:
            A dictionary with "thinking" and "action".
        """
        current_model = model_name if model_name else self.model

        system_prompt = """You are an expert web automation assistant. Your task is to analyze the provided information (user objective, overall context, and a description of the current screen/elements) and then decide the single next best action to take.

AVAILABLE ACTIONS:
- click(ELEMENT_DESCRIPTOR): Click on an element described by ELEMENT_DESCRIPTOR. Example: click("the 'Login' button").
- type("TEXT_TO_TYPE", into="ELEMENT_DESCRIPTOR"): Type the specified TEXT_TO_TYPE into an input field described by ELEMENT_DESCRIPTOR. Example: type("myusername", into="the username input field").
- press_key("KEY_NAME"): Simulate pressing a special key. KEY_NAME must be one of: "enter", "escape", "tab".
- navigate_to("URL_STRING"): Go to a specific web address. Example: navigate_to("https://www.example.com").
- COMPLETE: Use this action if the current user objective appears to be fully achieved.
- ERROR(REASON): Use this action if you cannot determine a valid next step or if the situation is unrecoverable.

RESPONSE FORMAT:
Respond with a JSON object matching this exact structure:
{
    "thinking": "Your detailed step-by-step reasoning. Explain how the provided screen description and context relate to the objective, and why you are choosing the specific action.",
    "action": "The chosen action string. Examples: click('the Login button'), type('hello world', into='the search input field'), press_key('enter'), COMPLETE, ERROR('Cannot find the specified element.')"
}

GUIDELINES:
1.  Carefully consider the `user_objective`, `current_context`, and `screen_description`.
2.  Choose the most logical and direct next action to progress towards the objective.
3.  For `click` and `type` actions, the `ELEMENT_DESCRIPTOR` should be based on the `screen_description`.
4.  If the objective is met, use `COMPLETE`.
5.  If you encounter an issue or cannot proceed, use `ERROR`.
"""

        user_prompt_parts = [f"Current Task/Objective: {user_objective}"]
        if current_context:
            user_prompt_parts.append(f"Overall Goal: {current_context}")
        if screen_description:
            user_prompt_parts.append(f"Current Screen Description: {screen_description}")
        else:
            user_prompt_parts.append("Current Screen Description: No visual information provided. Base your decision on the objective and context only.")

        user_prompt_text = "\n".join(user_prompt_parts)
        user_prompt_text += "\n\nAnalyze the situation and determine the single next action. Follow the response format strictly."

        try:
            response = self.client.chat(
                model=current_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt_text}
                ],
                format='json', # Request JSON output directly if supported by the Ollama version/model
                options={'temperature': 0.1}
            )

            content = response['message']['content']

            # Response should be a JSON string due to format='json'
            parsed_response = json.loads(content)
            if 'thinking' in parsed_response and 'action' in parsed_response:
                return parsed_response
            else:
                # Fallback if JSON is not as expected
                print(f"Ollama response content was not in expected JSON structure: {content}")
                return {"thinking": "Error: Ollama response was not in the expected JSON structure.", "action": "ERROR('Malformed response from AI')"}

        except Exception as e:
            print(f"Error in Ollama analyze_and_decide (model: {current_model}): {e}")
            # Check if the error is due to 'format' parameter not being supported
            if "Parameters: unknown parameter 'format'" in str(e) or "Unknown parameter 'format'" in str(e):
                 print("The connected Ollama version might not support the 'format' parameter for JSON output. Retrying without it.")
                 try:
                    response = self.client.chat(
                        model=current_model,
                        messages=[
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': user_prompt_text}
                        ],
                        options={'temperature': 0.1}
                    )
                    content = response['message']['content']
                    # Attempt to extract JSON from a potentially larger string
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        parsed_response = json.loads(json_str)
                        if 'thinking' in parsed_response and 'action' in parsed_response:
                            return parsed_response

                    # If not found, try to parse the whole content as JSON
                    try:
                        parsed_response = json.loads(content)
                        if 'thinking' in parsed_response and 'action' in parsed_response:
                             return parsed_response
                    except json.JSONDecodeError:
                        pass # Will fall through to the error return

                    print(f"Failed to parse JSON from Ollama response (after retry): {content}")
                    return {"thinking": f"Error: Could not parse JSON response from Ollama. Content: {content[:200]}...", "action": "ERROR('Malformed or non-JSON response from AI')"}

                 except Exception as retry_e:
                    print(f"Error in Ollama analyze_and_decide retry (model: {current_model}): {retry_e}")
                    return {"thinking": f"Error during Ollama request retry: {retry_e}", "action": f"ERROR('Ollama API request failed on retry: {retry_e}')"}

            return {"thinking": f"Error during Ollama request: {e}", "action": f"ERROR('Ollama API request failed: {e}')"}

    def analyze_state_vision(self, current_task: str, objective: str, model_name: str = None, screen_description: str = None) -> dict:
        """
        Analyzes a textual screen description in the context of the current_task and overall_objective.
        This is the text-based equivalent of MistralClient's analyze_state_vision.

        Args:
            current_task: The current task being attempted.
            objective: The overall user objective.
            model_name: The Ollama model to use (optional, defaults to client's model).
            screen_description: Textual description of the current screen state.

        Returns:
            A dictionary with "error", "task_completed", "objective_completed", and "summary".
        """
        current_model = model_name if model_name else self.model

        system_prompt = """You are an expert web page analysis agent. Your role is to meticulously analyze a provided textual description of a web page's state in the context of a current task and an overall objective.

Your response MUST be a JSON object with the following structure and data types:
{
    "error": "string_or_null",    // If the screen description indicates an error (e.g., 'Login failed', '404 Not Found') or the state is clearly unexpected, describe the error. Otherwise, this MUST be null.
    "task_completed": boolean,    // Based on the screen description and the 'Current Task', is this specific task now complete? This MUST be true or false.
    "objective_completed": boolean, // Considering the screen description and the 'Overall Objective', does it appear the entire objective has been achieved? This MUST be true or false.
    "summary": "string"           // A concise textual summary of the current page state as it relates to the task and objective. Describe what you infer from the text that is relevant.
}

GUIDELINES:
1.  Examine the `screen_description` thoroughly for any cues related to errors, task progression, or objective achievement.
2.  Pay close attention to the wording of the 'Current Task' and 'Overall Objective'.
3.  `task_completed` refers to the *specific* task provided, not the overall objective.
4.  `objective_completed` refers to the *entire* multi-step objective.
5.  If you are unsure about a boolean field, err on the side of `false` and explain your reasoning in the `summary`.
6.  The `summary` should be brief but informative, justifying your boolean decisions.
7.  Strictly adhere to the JSON format. Ensure `task_completed` and `objective_completed` are actual boolean values (true/false), not strings. `error` must be a string or null.
"""

        user_prompt_parts = [
            f"Current Task: \"{current_task}\"",
            f"Overall Objective: \"{objective}\""
        ]
        if screen_description:
            user_prompt_parts.append(f"Current Screen Description: \"{screen_description}\"")
        else:
            user_prompt_parts.append("Current Screen Description: No visual information provided. Base your decision on the task and objective only.")

        user_message_text = "CONTEXT FOR ANALYSIS:\n" + "\n".join(user_prompt_parts)
        user_message_text += "\n\nPlease analyze the provided information based on the system instructions. Provide your analysis STRICTLY in the specified JSON format."

        default_error_response = {
            "error": "Failed to parse analysis from model or API error.",
            "task_completed": False,
            "objective_completed": False,
            "summary": "Could not obtain analysis due to an error."
        }

        try:
            response = self.client.chat(
                model=current_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message_text}
                ],
                format='json',
                options={'temperature': 0.1}
            )

            content = response['message']['content']
            parsed_json = json.loads(content)

            if not all(key in parsed_json for key in ["error", "task_completed", "objective_completed", "summary"]):
                print(f"Ollama vision response missing required JSON keys. Response: {content}")
                # Salvage what we can
                salvaged_response = {
                    "error": parsed_json.get("error", "Model response missing 'error' key."),
                    "task_completed": parsed_json.get("task_completed", False),
                    "objective_completed": parsed_json.get("objective_completed", False),
                    "summary": parsed_json.get("summary", "Model response incomplete.")
                }
                if not isinstance(salvaged_response["task_completed"], bool): salvaged_response["task_completed"] = str(salvaged_response["task_completed"]).lower() == 'true'
                if not isinstance(salvaged_response["objective_completed"], bool): salvaged_response["objective_completed"] = str(salvaged_response["objective_completed"]).lower() == 'true'
                return salvaged_response

            parsed_json["task_completed"] = str(parsed_json.get("task_completed", "false")).lower() == "true"
            parsed_json["objective_completed"] = str(parsed_json.get("objective_completed", "false")).lower() == "true"
            return parsed_json

        except Exception as e:
            print(f"Error in Ollama analyze_state_vision (model: {current_model}): {e}")
            if "Parameters: unknown parameter 'format'" in str(e) or "Unknown parameter 'format'" in str(e):
                print("The connected Ollama version might not support the 'format' parameter for JSON output. Retrying without it.")
                try:
                    response = self.client.chat(
                        model=current_model,
                        messages=[
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': user_message_text}
                        ],
                        options={'temperature': 0.1}
                    )
                    content = response['message']['content']
                    # Attempt to extract JSON from a potentially larger string
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        parsed_json = json.loads(json_str)
                        if all(key in parsed_json for key in ["error", "task_completed", "objective_completed", "summary"]):
                            parsed_json["task_completed"] = str(parsed_json.get("task_completed", "false")).lower() == "true"
                            parsed_json["objective_completed"] = str(parsed_json.get("objective_completed", "false")).lower() == "true"
                            return parsed_json

                    # If not found, try to parse the whole content as JSON
                    try:
                        parsed_json = json.loads(content)
                        if all(key in parsed_json for key in ["error", "task_completed", "objective_completed", "summary"]):
                            parsed_json["task_completed"] = str(parsed_json.get("task_completed", "false")).lower() == "true"
                            parsed_json["objective_completed"] = str(parsed_json.get("objective_completed", "false")).lower() == "true"
                            return parsed_json
                    except json.JSONDecodeError:
                         pass # Fall through

                    print(f"Failed to parse JSON from Ollama vision response (after retry): {content}")
                    default_error_response["error"] = f"Failed to parse JSON response from Ollama (retry). Content: {content[:200]}..."
                    return default_error_response
                except Exception as retry_e:
                    print(f"Error in Ollama analyze_state_vision retry (model: {current_model}): {retry_e}")
                    default_error_response["error"] = f"Generic error in Ollama vision analysis retry: {retry_e}"
                    return default_error_response

            default_error_response["error"] = f"Generic error in Ollama vision analysis: {e}"
            return default_error_response

# Example Usage (for testing purposes, normally not here)
if __name__ == '__main__':
    print("Testing OllamaClient...")
    # Ensure Ollama server is running (e.g., `ollama serve`)
    # And the model is pulled (e.g., `ollama pull llama2`)

    # Test with default host and model
    client = OllamaClient()
    # Test with a specific host if your Ollama is running elsewhere
    # client = OllamaClient(host='http://your_ollama_server_ip:11434')


    print(f"Testing connection to {client.host}...")
    if client.test_connection():
        print("Connection successful.")

        # Test step generation
        print("\nTesting step generation...")
        objective = "Log into example.com and navigate to the user dashboard."
        steps = client.generate_steps_for_todo(objective)
        if steps:
            print(f"Generated steps for '{objective}':")
            for i, step in enumerate(steps):
                print(f"{i+1}. {step}")
        else:
            print(f"Failed to generate steps for '{objective}'.")

        # Test analyze_and_decide
        print("\nTesting analyze_and_decide...")
        screen_info = "The page shows a login form with fields for 'username' and 'password', and a 'Login' button."
        decision = client.analyze_and_decide(
            user_objective="Enter username 'testuser'.",
            current_context=objective,
            screen_description=screen_info
        )
        print(f"Decision for '{objective}' with screen info '{screen_info[:50]}...':")
        print(json.dumps(decision, indent=2))

        # Test analyze_state_vision (text-based equivalent)
        print("\nTesting analyze_state_vision...")
        state_analysis = client.analyze_state_vision(
            current_task="Verify login was successful.",
            objective=objective,
            screen_description="The page shows 'Welcome testuser!' and a link to 'Dashboard'."
        )
        print(f"State analysis result:")
        print(json.dumps(state_analysis, indent=2))

    else:
        print(f"Connection to Ollama server at {client.host} failed. Ensure Ollama is running and the model '{client.model}' is available.")
