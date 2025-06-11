import google.generativeai as genai
import os
import json
import base64
import re
from PIL import Image
import io
from google.api_core import exceptions as google_exceptions # For specific error handling

class GoogleClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key is required. Set it as an environment variable GOOGLE_API_KEY or pass it to the constructor.")
        try:
            genai.configure(api_key=self.api_key)
        except Exception as e:
            raise ValueError(f"Failed to configure Google AI client: {e}")
        self.default_text_model = "gemini-1.5-flash-latest"
        self.default_vision_model = "gemini-1.5-flash-latest" # This model is multimodal

    def generate_steps_for_todo(self, user_prompt: str, model_name: str = None) -> list[str]:
        model_to_use = model_name or self.default_text_model
        # System prompt is part of the main prompt for Gemini's generate_content
        system_prompt_instructions = """You are an expert planning agent. Your primary function is to break down a user's high-level web automation objective into a detailed, ordered list of specific sub-tasks. These sub-tasks will be executed by an automation tool.
GUIDELINES:
1. Analyze the user's objective carefully.
2. Generate a sequence of actionable steps. Each step should be a concrete action (e.g., "Navigate to URL", "Click the 'Login' button", "Type 'search query' into the search bar", "Verify that the text 'Welcome User' is visible") or a verification point.
3. For moderately complex objectives, aim for 10-15 granular steps. For very complex objectives, more steps may be necessary. For simple objectives, fewer steps are fine.
4. The steps should be logical and follow a sequence that a human would perform to achieve the objective.
5. Each step must be a clear, concise instruction.
6. Consider edge cases or common issues if applicable (e.g., "Check for login errors before proceeding"). This is optional but helpful.
OUTPUT FORMAT:
Present the steps as a simple list of strings, with each step on a new line. Each step must start with '- ' (a hyphen followed by a space).
Example for objective "Log into the website example.com and go to the dashboard":
- Navigate to https://example.com
- Click the 'Login' link or button.
- Type 'testuser' into the username field.
- Type 'password123' into the password field.
- Click the 'Submit' or 'Login' button.
- Verify that the page shows 'Welcome testuser' or similar.
- Click on the 'Dashboard' link in the navigation menu.
- Verify that the dashboard page is loaded by checking for 'User Dashboard' title."""

        full_prompt = f"{system_prompt_instructions}\n\nUser objective: {user_prompt}"
        try:
            model = genai.GenerativeModel(model_to_use)
            response = model.generate_content(full_prompt)
            content = response.text # Directly get text
            steps = []
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    steps.append(line[2:].strip())
                elif line:
                    steps.append(line)
            return steps
        except Exception as e:
            print(f"Error generating steps with Google (model: {model_to_use}): {e}")
            return []

    def analyze_state_vision(self, image_base64: str, current_task: str, objective: str, model_name: str = None) -> dict:
        model_to_use = model_name or self.default_vision_model
        # System prompt is part of the main prompt for Gemini's generate_content
        system_prompt_instructions = """You are an expert web page analysis agent. Your role is to meticulously analyze a provided screenshot of a web page in the context of a current task and an overall objective.
Your response MUST be a single, valid JSON object string. Do NOT include markdown specifiers like ```json ... ``` or any other text outside the JSON object.
The JSON object must have the following structure and data types:
{
    "error": "string_or_null",
    "task_completed": boolean,
    "objective_completed": boolean,
    "summary": "string"
}
GUIDELINES FOR JSON VALUES:
- "error": Describe any error state visible (e.g., "Login failed due to invalid credentials", "The requested item is out of stock"). If no error is apparent, set to null.
- "task_completed": Set to true if the specific `current_task` appears to be successfully completed based on the visual evidence in the screenshot. Otherwise, set to false.
- "objective_completed": Set to true if the overall `objective` appears to be fully achieved. Otherwise, set to false.
- "summary": Provide a concise textual summary of your analysis, explaining your reasoning for the "task_completed" and "objective_completed" statuses and any error identified.
"""
        text_prompt = f"CONTEXT FOR ANALYSIS:\nCurrent Task: \"{current_task}\"\nOverall Objective: \"{objective}\"\n\nPlease analyze the provided screenshot based on the system instructions and context. Provide your analysis STRICTLY in the specified JSON format."
        default_error_response = {"error": "Failed to analyze state or parse AI response.", "task_completed": False, "objective_completed": False, "summary": "Could not obtain analysis."}
        response_text = ""

        try:
            image_bytes = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(image_bytes))

            model = genai.GenerativeModel(model_to_use)
            prompt_parts = [system_prompt_instructions, img, text_prompt]

            response = model.generate_content(prompt_parts)
            response_text = response.text

            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    parsed_json = json.loads(json_str)
                    if all(key in parsed_json for key in ["error", "task_completed", "objective_completed", "summary"]):
                        parsed_json["task_completed"] = str(parsed_json.get("task_completed", "false")).lower() == "true"
                        parsed_json["objective_completed"] = str(parsed_json.get("objective_completed", "false")).lower() == "true"
                        error_val = parsed_json.get("error")
                        if isinstance(error_val, str) and error_val.lower() in ["null", "none"]:
                            parsed_json["error"] = None
                        elif not error_val: # Handles empty string or actual None if model returns that for null
                            parsed_json["error"] = None
                        return parsed_json
                    else:
                        default_error_response["summary"] = "AI response JSON (Google) missing required keys."
                        default_error_response["raw_ai_output"] = response_text
                        return default_error_response
                except json.JSONDecodeError as je:
                    default_error_response["summary"] = f"Failed to decode JSON from Google response: {je}"
                    default_error_response["raw_ai_output"] = response_text
                    return default_error_response
            else:
                default_error_response["summary"] = "No valid JSON object found in Google AI response."
                default_error_response["raw_ai_output"] = response_text
                return default_error_response
        except Exception as e:
            print(f"Error in analyze_state_vision with Google (model: {model_to_use}): {e}")
            default_error_response["error"] = f"API call failed: {str(e)}"
            return default_error_response

    def analyze_and_decide(self, image_base64: str, user_objective: str, model_name: str = None, current_context: str = None) -> dict:
        model_to_use = model_name or self.default_vision_model
        system_prompt_instructions = """You are an expert web automation assistant. Your task is to analyze the provided screenshot of a web page, along with the user's current objective and overall goal, and decide the single next best action to perform.

AVAILABLE ACTIONS:
1.  `click(INDEX)`: Click on an element identified by its numerical index shown on the screenshot. Example: `click(3)`
2.  `type("TEXT_TO_TYPE", into="DESCRIPTOR")`: Type text into an input field. `DESCRIPTOR` should be a short description of the target field (e.g., "username field", "search bar", "item quantity input with current value 2"). Example: `type("hello world", into="search bar")`
3.  `press_key("KEY_NAME")`: Press a special key. Supported keys: "enter", "escape", "tab". Example: `press_key("enter")`
4.  `navigate_to("URL")`: Navigate to a specific URL. Example: `navigate_to("https://www.example.com")`
5.  `COMPLETE`: If the user's current objective/task seems to be fully achieved based on the screenshot.
6.  `ERROR("REASON")`: If you cannot determine a valid action or encounter an issue. Example: `ERROR("Button not found")`

RESPONSE FORMAT:
You MUST respond with a single, valid JSON object string. Do NOT include markdown specifiers like ```json ... ``` or any other text outside the JSON object.
The JSON object must have two keys:
- "thinking": A brief step-by-step thought process explaining your reasoning for the chosen action. This should be detailed enough to understand your decision-making process.
- "action": The chosen action string from the available actions.

Example:
{
  "thinking": "The user wants to log in. The screenshot shows a username field (index 1) and a password field (index 2), and a login button (index 3). I should first type the username 'testuser' into the username field.",
  "action": "type(\\"testuser\\", into=\\"username field with index 1\\")"
}
"""
        text_prompt = f"Current Task/Objective: {user_objective}\nOverall Goal: {current_context if current_context else 'Not specified'}\n\nAnalyze the screenshot and determine the next action. Respond in the specified JSON format."
        default_error_response = {"thinking": "Error: Could not parse AI response or response incomplete.", "action": "ERROR('Malformed response from AI or internal error')"}
        response_text = ""

        try:
            image_bytes = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(image_bytes))

            model = genai.GenerativeModel(model_to_use)
            prompt_parts = [system_prompt_instructions, img, text_prompt]

            response = model.generate_content(prompt_parts)
            response_text = response.text

            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    parsed_json = json.loads(json_str)
                    if all(key in parsed_json for key in ["thinking", "action"]):
                        return parsed_json
                    else:
                        default_error_response["thinking"] = "AI response JSON (Google) missing required keys (thinking/action)."
                        default_error_response["raw_ai_output"] = response_text
                        return default_error_response
                except json.JSONDecodeError as je:
                    default_error_response["thinking"] = f"Failed to decode JSON from Google decision response: {je}"
                    default_error_response["raw_ai_output"] = response_text
                    return default_error_response
            else:
                default_error_response["thinking"] = "No valid JSON object found in Google AI decision response."
                default_error_response["raw_ai_output"] = response_text
                return default_error_response
        except Exception as e:
            print(f"Error in analyze_and_decide with Google (model: {model_to_use}): {e}")
            default_error_response["thinking"] = f"API call failed during decision: {str(e)}"
            return default_error_response

    def test_connection(self):
        try:
            model = genai.GenerativeModel(self.default_text_model)
            response = model.generate_content("Hello, world from Google AI test")
            _ = response.text # Access text to ensure generation occurred
            return True
        except google_exceptions.Unauthenticated:
            print(f"Google UnauthenticatedError (model: {self.default_text_model}): API key is invalid or not authorized.")
            return False
        except google_exceptions.ResourceExhausted:
            print(f"Google ResourceExhaustedError (model: {self.default_text_model}): Rate limit exceeded or quota issue.")
            return False
        except Exception as e:
            print(f"Failed to connect to Google AI (model: {self.default_text_model}): {e}")
            return False
