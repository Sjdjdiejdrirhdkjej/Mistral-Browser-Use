import json
from transformers import pipeline
import re # For simple fallback extraction if JSON parsing fails

class XenovaClient:
    def __init__(self):
        self.text_pipe = None
        try:
            self.text_pipe = pipeline('text2text-generation', model='google/flan-t5-base', tokenizer='google/flan-t5-base', device=-1)
            print("Text generation pipeline (google/flan-t5-base) initialized successfully.")
        except Exception as e:
            print(f"Error initializing Xenova text generation pipeline: {e}")
            # self.text_pipe remains None

    def _parse_json_from_text_pipe(self, generated_text: str, expected_keys: list) -> dict:
        """
        Helper function to parse JSON from the text pipeline's output.
        Uses regex to find a JSON-like string and then attempts to parse it.
        """
        try:
            # Use regex to find a string that looks like a JSON object
            match = re.search(r'\{.*\}', generated_text, re.DOTALL)

            if match:
                json_str = match.group(0)
                # Basic cleaning of the JSON string - T5 might escape quotes
                json_str = json_str.replace('\\n', '\n').replace('\\"', '"')

                parsed_json = json.loads(json_str)

                if all(key in parsed_json for key in expected_keys):
                    return parsed_json
                else:
                    print(f"Error: Missing one or more expected keys ({expected_keys}) in parsed JSON: {json_str}")
                    return None # Indicates parsing succeeded but content is invalid
            else:
                print(f"Error: No valid JSON object found using regex in AI response: {generated_text}")
                return None # Indicates no JSON found
        except json.JSONDecodeError as je:
            print(f"Error decoding JSON from AI response (after regex extraction): {je}. Extracted string was: {json_str if 'json_str' in locals() else 'N/A'}. Original response: {generated_text}")
            return None # Indicates JSON decoding error
        except Exception as e:
            print(f"An unexpected error occurred during JSON parsing: {e}")
            return None

    def generate_steps_for_todo(self, user_prompt: str) -> list[str]:
        if not self.text_pipe:
            print("Error: Xenova text_pipe not initialized for generate_steps_for_todo.")
            return []

        # Prompt designed for T5 to generate a list of steps
        prompt = f"Break down the following user request into a concise list of actionable steps. Each step should begin with '- '. User request: \"{user_prompt}\""
        try:
            # max_length might need adjustment based on typical output.
            # num_beams and early_stopping are standard for better quality generation.
            generated_output = self.text_pipe(prompt, max_length=250, num_beams=4, early_stopping=True)
            generated_text = generated_output[0]['generated_text']

            # Process the generated text to extract steps
            steps = []
            for line in generated_text.split('\n'):
                stripped_line = line.strip()
                if stripped_line.startswith("- "):
                    steps.append(stripped_line[2:].strip()) # Remove "- " prefix
                elif stripped_line: # Capture non-empty lines if no prefix, as a fallback
                    steps.append(stripped_line)

            if not steps and generated_text: # If no "- " prefix was found but there's output
                print("Warning: Steps generated but no '- ' prefix found. Using raw lines.")
                steps = [line.strip() for line in generated_text.split('\n') if line.strip()]

            return steps
        except Exception as e:
            print(f"Error generating steps with text_pipe: {e}")
            return []

    def analyze_state_vision(self, current_task: str, objective: str, ocr_text: str, screen_description: str = None) -> dict:
        default_error_response = {"error": "Failed to analyze state or parse AI response.", "task_completed": False, "objective_completed": False, "summary": "Could not obtain analysis due to an internal error."}

        if not self.text_pipe:
            print("Error: Xenova text_pipe not initialized for analyze_state_vision.")
            return {**default_error_response, "error": "Text pipeline not initialized."}

        prompt = f"""Analyze the current state based on the provided information to determine task and objective completion.
Current Task: {current_task}
Overall Objective: {objective}
Text from Screen (OCR): {ocr_text if ocr_text else "No text extracted from screen."}
Additional Context/Screen Description: {screen_description if screen_description else "None"}

You MUST respond ONLY with a valid JSON object. Do not include any text before or after the JSON. The JSON object must have the following keys: "error" (string or null for no error), "task_completed" (boolean), "objective_completed" (boolean), and "summary" (string, your reasoning for the status).
Example: {{"error": null, "task_completed": false, "objective_completed": false, "summary": "The login form is visible based on OCR text."}}
"""
        try:
            generated_output = self.text_pipe(prompt, max_length=400, num_beams=5, early_stopping=True, temperature=0.7)
            generated_text = generated_output[0]['generated_text']

            parsed_analysis = self._parse_json_from_text_pipe(generated_text, ["error", "task_completed", "objective_completed", "summary"])

            if parsed_analysis:
                # Ensure boolean conversion for task_completed and objective_completed
                parsed_analysis["task_completed"] = str(parsed_analysis.get("task_completed", "false")).lower() == "true"
                parsed_analysis["objective_completed"] = str(parsed_analysis.get("objective_completed", "false")).lower() == "true"

                # Ensure error is null if model outputs "null" as string
                if isinstance(parsed_analysis.get("error"), str) and parsed_analysis["error"].lower() == "null":
                    parsed_analysis["error"] = None

                return parsed_analysis
            else:
                # _parse_json_from_text_pipe already printed an error
                error_response = default_error_response.copy()
                error_response["summary"] = "AI response was not valid JSON or missed keys. See raw_ai_output."
                error_response["raw_ai_output"] = generated_text[:500] # Include raw output
                return error_response

        except Exception as e:
            print(f"Error in analyze_state_vision with text_pipe: {e}")
            return {**default_error_response, "error": f"Exception during AI call: {str(e)}"}

    def analyze_and_decide(self, user_objective: str, ocr_text: str, current_context: str = None, screen_description: str = None) -> dict:
        default_error_response = {"thinking": "Error: Could not parse AI response or response incomplete.", "action": "ERROR('Malformed response from AI or internal error')"}

        if not self.text_pipe:
            print("Error: Xenova text_pipe not initialized for analyze_and_decide.")
            return {**default_error_response, "thinking": "Text pipeline not initialized."}

        prompt = f"""Given the current situation, decide the next single action.
User Objective: {user_objective}
Overall Goal: {current_context if current_context else "Not specified."}
Text from Screen (OCR): {ocr_text if ocr_text else "No text extracted from screen."}
Additional Context/Screen Description: {screen_description if screen_description else "None"}

You MUST respond ONLY with a valid JSON object. Do not include any text before or after the JSON. The JSON object must have the keys: "thinking" (your reasoning) and "action" (the command to execute, e.g., click('button_id'), type('text', into='field_name'), complete(), error('reason')).
Example: {{"thinking": "The user wants to log in, OCR shows 'username' and 'password' fields. I should type username.", "action": "type('my_username', into='username field')"}}
"""
        try:
            generated_output = self.text_pipe(prompt, max_length=400, num_beams=5, early_stopping=True, temperature=0.7)
            generated_text = generated_output[0]['generated_text']

            parsed_decision = self._parse_json_from_text_pipe(generated_text, ["thinking", "action"])

            if parsed_decision:
                return parsed_decision
            else:
                # Fallback: try to extract action and thinking using regex if JSON parsing completely fails
                # This is a last resort and indicates issues with the model's JSON generation.
                print(f"Warning: JSON parsing failed for decision. Attempting regex fallback. AI Response: {generated_text[:200]}...")
                try:
                    thinking_match = re.search(r'"thinking":\s*"([^"]*)"', generated_text, re.IGNORECASE | re.DOTALL)
                    action_match = re.search(r'"action":\s*"([^"]*)"', generated_text, re.IGNORECASE | re.DOTALL)

                    thinking = thinking_match.group(1).strip() if thinking_match else "Could not extract thinking (JSON parse failed)."
                    action = action_match.group(1).strip() if action_match else "ERROR('Could not extract action (JSON parse failed)')"

                    if action != "ERROR('Could not extract action (JSON parse failed)')":
                         print("Regex fallback successfully extracted action/thinking.")
                         return {"thinking": thinking, "action": action}
                    else:
                        print("Regex fallback also failed to extract required fields.")
                        error_response = default_error_response.copy()
                        error_response["thinking"] = "AI response was not valid JSON and fallbacks failed. See raw_ai_output."
                        error_response["raw_ai_output"] = generated_text[:500] # Include raw output
                        return error_response
                except Exception as fallback_e:
                    print(f"Error during regex fallback extraction: {fallback_e}")
                    error_response = default_error_response.copy()
                    error_response["thinking"] = f"AI response was not valid JSON, regex fallback failed: {fallback_e}. See raw_ai_output."
                    error_response["raw_ai_output"] = generated_text[:500] # Include raw output
                    return error_response

        except Exception as e:
            print(f"Error in analyze_and_decide with text_pipe: {e}")
            error_response = default_error_response.copy()
            error_response["thinking"] = f"Exception during AI call: {str(e)}. See raw_ai_output."
            # It's possible generated_text is not defined here if error is before AI call
            error_response["raw_ai_output"] = generated_text[:500] if 'generated_text' in locals() else "N/A"
            return error_response

# Example Usage (for testing individual methods - not part of the class)
if __name__ == '__main__':
    client = XenovaClient()

    if not client.text_pipe:
        print("Cannot run tests: XenovaClient text_pipe failed to initialize.")
    else:
        print("\n--- Testing generate_steps_for_todo ---")
        steps = client.generate_steps_for_todo("Log into my account on example.com and then check my messages for any new notifications.")
        print(f"Generated steps: {steps}")

        print("\n--- Testing analyze_state_vision ---")
        ocr_example_text = "Welcome, User!\nYour last login was yesterday.\nNew messages: 3\n[Logout Button]"
        analysis = client.analyze_state_vision(
            current_task="Verify login success and check for new messages",
            objective="Log into account and check messages",
            ocr_text=ocr_example_text,
            screen_description="Dashboard page after login."
        )
        print(f"State analysis result: {json.dumps(analysis, indent=2)}")

        print("\n--- Testing analyze_and_decide ---")
        ocr_login_page_text = "Username:\nPassword:\n[Login Button]\n[Forgot Password Link]"
        decision = client.analyze_and_decide(
            user_objective="Enter username 'testuser'",
            ocr_text=ocr_login_page_text,
            current_context="Attempting to log into the website.",
            screen_description="Currently on the main login page."
        )
        print(f"Decision result: {json.dumps(decision, indent=2)}")

        decision_on_dashboard = client.analyze_and_decide(
            user_objective="Find and click the 'New Messages' notification or link.",
            ocr_text=ocr_example_text, # From previous state analysis
            current_context="Logged in, now looking for messages.",
            screen_description="User dashboard with welcome message and message count."
        )
        print(f"Decision on dashboard result: {json.dumps(decision_on_dashboard, indent=2)}")

        print("\n--- Test with empty/problematic OCR ---")
        analysis_no_ocr = client.analyze_state_vision(
            current_task="Check if login page loaded",
            objective="Navigate to login page",
            ocr_text="",
            screen_description="Just navigated, expecting login elements."
        )
        print(f"State analysis with empty OCR: {json.dumps(analysis_no_ocr, indent=2)}")

        decision_no_ocr = client.analyze_and_decide(
            user_objective="Find the login button",
            ocr_text=None, # Simulating None or empty
            current_context="Trying to log in",
            screen_description="Login page"
        )
        print(f"Decision with no OCR: {json.dumps(decision_no_ocr, indent=2)}")
