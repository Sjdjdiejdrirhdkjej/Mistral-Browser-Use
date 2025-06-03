import json
from transformers import pipeline

class XenovaClient:
    def __init__(self):
        try:
            self.pipe = pipeline('text2text-generation', model='XFTransformations/gte-small', tokenizer='XFTransformations/gte-small', device=-1)
        except Exception as e:
            print(f"Error initializing Xenova client: {e}")
            self.pipe = None

    def generate_steps_for_todo(self, user_prompt: str) -> list[str]:
        if not self.pipe:
            print("Error: Xenova client not initialized.")
            return []

        prompt = f"Break down the following task into actionable steps, each starting with '- ':\n{user_prompt}"
        try:
            generated_text = self.pipe(prompt, max_length=200, num_beams=4, early_stopping=True)[0]['generated_text']
            steps = [step.strip() for step in generated_text.split('\n') if step.strip().startswith("- ")]
            # Remove the leading "- "
            steps = [step[2:].strip() for step in steps if len(step) > 2]
            if not steps and generated_text: # Fallback if no "- " prefix is found but there is output
                steps = [line.strip() for line in generated_text.split('\n') if line.strip()]
            return steps
        except Exception as e:
            print(f"Error generating steps: {e}")
            return []

    def analyze_and_decide(self, user_objective: str, current_context: str = None, screen_description: str = None) -> dict:
        if not self.pipe:
            print("Error: Xenova client not initialized.")
            return {"thinking": "Error: Xenova client not initialized.", "action": "ERROR('Xenova client not initialized')"}

        prompt_parts = [f"Objective: {user_objective}"]
        if current_context:
            prompt_parts.append(f"Current Context: {current_context}")
        if screen_description:
            prompt_parts.append(f"Screen Description: {screen_description}")

        prompt_parts.append("Based on the above, what is the next single action to take? Respond in JSON format with 'thinking' and 'action' keys. For example: {\"thinking\": \"I should click the login button.\", \"action\": \"click('Login button')\"}")
        prompt = "\n".join(prompt_parts)

        try:
            generated_text = self.pipe(prompt, max_length=300, num_beams=5, early_stopping=True)[0]['generated_text']
            # Try to find JSON within the generated text
            json_start = generated_text.find('{')
            json_end = generated_text.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_str = generated_text[json_start:json_end]
                # Basic cleaning of the JSON string
                json_str = json_str.replace('\\n', '\n').replace('\\"', '"')
                try:
                    decision = json.loads(json_str)
                    if "thinking" in decision and "action" in decision:
                        return decision
                    else:
                        print(f"Error: Missing 'thinking' or 'action' in response: {json_str}")
                        return {"thinking": "Error: Could not parse AI response or response incomplete.", "action": "ERROR('Malformed response from AI - missing keys')"}
                except json.JSONDecodeError as je:
                    print(f"Error decoding JSON from AI response: {je}. Response was: {json_str}")
                    # Fallback: try to extract action and thinking using string manipulation if JSON parsing fails
                    thinking = "Could not extract thinking."
                    action = "ERROR('Malformed response from AI - JSON decode error')"
                    if "thinking" in generated_text and "action" in generated_text:
                         # This is a very basic fallback, might not be robust
                        try:
                            thinking_start = generated_text.lower().find('"thinking": "') + len('"thinking": "')
                            thinking_end = generated_text.lower().find('"', thinking_start)
                            thinking = generated_text[thinking_start:thinking_end]

                            action_start = generated_text.lower().find('"action": "') + len('"action": "')
                            action_end = generated_text.lower().find('"', action_start)
                            action = generated_text[action_start:action_end]
                        except Exception:
                            pass # Stick to default error if extraction fails
                    return {"thinking": thinking, "action": action}

            else:
                print(f"Error: No JSON object found in AI response: {generated_text}")
                return {"thinking": "Error: Could not parse AI response, no JSON found.", "action": "ERROR('Malformed response from AI - no JSON found')"}

        except Exception as e:
            print(f"Error in analyze_and_decide: {e}")
            return {"thinking": "Error: Exception during AI call.", "action": "ERROR('Exception during AI call')"}

    def analyze_state_vision(self, current_task: str, objective: str, screen_description: str = None) -> dict:
        if not self.pipe:
            print("Error: Xenova client not initialized.")
            return {"error": "Xenova client not initialized.", "task_completed": False, "objective_completed": False, "summary": "Could not obtain analysis."}

        prompt_parts = [
            f"Current Task: {current_task}",
            f"Overall Objective: {objective}",
        ]
        if screen_description:
            prompt_parts.append(f"Current Screen Description: {screen_description}")

        prompt_parts.append(
            "Analyze the current state. Respond in JSON format with 'error' (string or null), 'task_completed' (boolean), 'objective_completed' (boolean), and 'summary' (string) keys. "
            "For example: {\"error\": null, \"task_completed\": false, \"objective_completed\": false, \"summary\": \"Still working on logging in.\"}"
        )
        prompt = "\n".join(prompt_parts)

        default_error_response = {"error": "Failed to parse analysis from model.", "task_completed": False, "objective_completed": False, "summary": "Could not obtain analysis."}

        try:
            generated_text = self.pipe(prompt, max_length=350, num_beams=5, early_stopping=True)[0]['generated_text']
            json_start = generated_text.find('{')
            json_end = generated_text.rfind('}') + 1

            if json_start != -1 and json_end != -1:
                json_str = generated_text[json_start:json_end]
                json_str = json_str.replace('\\n', '\n').replace('\\"', '"') # Basic cleaning
                try:
                    analysis = json.loads(json_str)

                    # Validate and type cast
                    parsed_error = analysis.get("error")
                    if isinstance(parsed_error, str) and parsed_error.lower() == "null":
                        analysis["error"] = None
                    elif not isinstance(parsed_error, (str, type(None))):
                         print(f"Warning: 'error' field is not a string or null: {parsed_error}")
                         analysis["error"] = str(parsed_error) # cast to string if not null

                    task_completed_str = str(analysis.get("task_completed", "false")).lower()
                    analysis["task_completed"] = task_completed_str == "true"

                    objective_completed_str = str(analysis.get("objective_completed", "false")).lower()
                    analysis["objective_completed"] = objective_completed_str == "true"

                    if not isinstance(analysis.get("summary"), str):
                        analysis["summary"] = str(analysis.get("summary", "Summary not provided."))

                    if "error" in analysis and "task_completed" in analysis and \
                       "objective_completed" in analysis and "summary" in analysis:
                        return analysis
                    else:
                        print(f"Error: Missing keys in analysis response: {json_str}")
                        return default_error_response
                except json.JSONDecodeError as je:
                    print(f"Error decoding JSON for analysis: {je}. Response was: {json_str}")
                    return default_error_response
            else:
                print(f"Error: No JSON object found in AI analysis response: {generated_text}")
                return default_error_response
        except Exception as e:
            print(f"Error in analyze_state_vision: {e}")
            return default_error_response
