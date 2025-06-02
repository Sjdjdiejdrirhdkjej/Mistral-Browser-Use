import ollama
import requests
import subprocess
import json # For parsing streaming output if necessary

class OllamaClient:
    def __init__(self, host='http://localhost:11434'):
        self.client = ollama.Client(host=host)

    def list_models(self):
        """Fetches available local models from Ollama."""
        try:
            models = self.client.list()
            return models.get('models', [])
        except requests.exceptions.ConnectionError:
            print(f"Error: Could not connect to Ollama at {self.client._client.host}. Please ensure Ollama is running.")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while listing models: {e}")
            return []

    def is_model_available(self, model_name: str) -> bool:
        """Checks if a specific model is available locally."""
        try:
            local_models = self.list_models()
            # Ollama model names can be like 'llama3.2:latest', so check startswith
            return any(m['name'].startswith(model_name) for m in local_models)
        except Exception as e:
            print(f"Error checking model availability for {model_name}: {e}")
            return False

    def pull_model(self, model_name: str) -> tuple[bool, str]:
        """
        Pulls a model using 'ollama pull <model_name>'.
        Returns (success: bool, message: str).
        """
        try:
            print(f"Attempting to pull model: {model_name}...")
            # Using subprocess.run to capture output and wait for completion.
            # The ollama CLI streams JSON objects for progress.
            # We can capture stderr for errors and check the final status.
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line buffered
                encoding='utf-8'
            )

            # Stream output for progress (optional, but good for user feedback if this were a UI)
            # For now, we'll just wait for completion and check stderr for errors.
            # This simple version might not show detailed progress in Streamlit easily.
            # A more advanced version might use st.write to stream progress.

            # Example of how to read stdout line by line if needed:
            # while True:
            #     output = process.stdout.readline()
            #     if output == '' and process.poll() is not None:
            #         break
            #     if output:
            #         try:
            #             # Ollama pull often streams JSON status objects
            #             status = json.loads(output.strip())
            #             # print(status.get("status")) # Or update a Streamlit element
            #         except json.JSONDecodeError:
            #             print(output.strip()) # Fallback for non-JSON lines

            stdout, stderr = process.communicate() # Wait for process to complete

            if process.returncode == 0:
                # Check stderr for any "already exists" messages, which are not errors
                if "already exists" in stderr.lower():
                    msg = f"Model '{model_name}' already exists locally."
                    print(msg)
                    return True, msg
                msg = f"Successfully pulled model '{model_name}'."
                print(msg)
                # Verify by listing models again (optional, but good for confirmation)
                if not self.is_model_available(model_name):
                     msg = f"Model '{model_name}' pull reported success, but not found in list. Check Ollama."
                     print(msg)
                     return False, msg # Or True if pull command itself was successful
                return True, msg
            else:
                error_message = f"Failed to pull model '{model_name}'. Error: {stderr.strip()}"
                if not stderr.strip() and stdout.strip(): # Sometimes error is on stdout
                    error_message = f"Failed to pull model '{model_name}'. Output: {stdout.strip()}"
                print(error_message)
                return False, error_message
        except FileNotFoundError:
            error_message = "Error: 'ollama' command not found. Please ensure Ollama is installed and in your PATH."
            print(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"An unexpected error occurred while pulling model '{model_name}': {e}"
            print(error_message)
            return False, error_message

    def generate_text(self, prompt, model_name='llama3.2'):
        """Generates text using the specified model and prompt."""
        try:
            response = self.client.generate(model=model_name, prompt=prompt)
            return response['response']
        except requests.exceptions.ConnectionError:
            print(f"Error: Could not connect to Ollama at {self.client._client.host}. Please ensure Ollama is running.")
            return "Error: Connection to Ollama failed."
        except ollama.ResponseError as e:
            if e.status_code == 404:
                print(f"Error: Model '{model_name}' not found. Please ensure the model is available in Ollama.")
                return f"Error: Model '{model_name}' not found."
            print(f"An API error occurred while generating text: {e}")
            return f"Error: API error occurred - {e.error}"
        except Exception as e:
            print(f"An unexpected error occurred while generating text: {e}")
            return "Error: An unexpected error occurred."

    def _parse_ollama_response(self, response_text: str, expected_keys: list) -> dict:
        """Helper to parse JSON from Ollama response and ensure keys."""
        try:
            # Ollama generate often returns a string that is a JSON object.
            # Sometimes it might be a stream of JSON objects if stream=True was used.
            # Assuming response_text is a single JSON string here.
            parsed_json = json.loads(response_text)
            if not isinstance(parsed_json, dict):
                # If llama3.2 (non-instruct) returns a plain string, try to make it valid JSON.
                # This is a fallback and might need model-specific handling.
                # A better approach is to use an instruct-tuned model and format the prompt for JSON.
                if isinstance(response_text, str):
                    # Try to find a JSON block within the string if the model adds extra text
                    match = re.search(r'{.*}', response_text, re.DOTALL)
                    if match:
                        parsed_json = json.loads(match.group(0))
                    else: # Fallback: wrap the raw string if it's not JSON-like
                         # This is a simple heuristic, might need more robust error handling
                        if all(key in response_text for key in expected_keys): # basic check
                             # if keys are present, assume it's a malformed json string
                             # this is very brittle.
                             print(f"Warning: Response was not valid JSON. Attempting to parse heuristically: {response_text}")
                             # Heuristic: if it looks like a dict but isn't valid json (e.g. from llama3 non-instruct)
                             # this is a guess and might fail.
                             # A better solution is to ensure the model ALWAYS returns valid JSON.
                             if expected_keys == ["thinking", "action"]:
                                 return {"thinking": "Could not parse thinking.", "action": response_text}
                             elif expected_keys == ["error", "task_completed", "objective_completed", "summary"]:
                                 return {"summary": response_text, "error": "Could not parse.", "task_completed": False, "objective_completed": False}
                             else: # for generate_steps_for_todo
                                 return {"steps": [response_text]}


                        print(f"Error: Response was not a JSON object: {response_text}")
                        return {"error_parsing": f"Response was not a JSON object: {response_text}"}

            # Ensure all expected keys are present, provide defaults if not
            for key in expected_keys:
                if key not in parsed_json:
                    # Provide a default value based on expected type or context
                    if key in ["thinking", "action", "summary", "error"]:
                        parsed_json[key] = f"Missing key in response: {key}"
                    elif key in ["task_completed", "objective_completed"]:
                        parsed_json[key] = False
                    elif key == "steps": # For generate_steps_for_todo
                        parsed_json[key] = []
            return parsed_json
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from Ollama response: {e}. Response: {response_text}")
            # Fallback for generate_steps_for_todo if direct list is expected and it's just a string
            if expected_keys == ["steps"] and isinstance(response_text, str) and response_text.startswith("["):
                try: # try to parse as list string
                    steps = json.loads(response_text)
                    if isinstance(steps, list): return {"steps": steps}
                except: pass # ignore if fails

            # Fallback for other specific cases if direct string output is acceptable for some fields
            if expected_keys == ["thinking", "action"]:
                 return {"thinking": "JSON parsing failed.", "action": response_text if isinstance(response_text, str) else "Invalid response format."}

            return {"error_parsing": f"JSONDecodeError: {e}. Response: {response_text}"}
        except Exception as e:
            print(f"Unexpected error parsing Ollama response: {e}. Response: {response_text}")
            return {"error_parsing": f"Unexpected error: {e}. Response: {response_text}"}


    def analyze_and_decide(self, image_path: str, current_task: str, current_objective: str, model_name: str = "llava") -> dict:
        """Analyzes an image and current task/objective to decide the next browser action using Ollama with a LLaVA model."""
        # This method assumes a LLaVA-like model is used (e.g., "llava", "bakllava")
        # These models can process both images and text.
        # The 'model_name' should be set to the specific LLaVA model installed in Ollama.

        system_prompt = """You are an AI assistant helping a user automate web browsing tasks.
You will be given a screenshot of the current web page, the user's overall objective, and the current specific task.
Your goal is to analyze the screenshot and the text provided to determine the next browser action.
The available browser actions are:
- click(element_index): Click on the element with the given index. Element indexes are visible in the screenshot.
- type("text_to_type", into="element_description_or_index"): Type the specified text into the described element (e.g., 'search input with current value "Search text"').
- navigate_to("url"): Navigate to the given URL.
- press_key("key_name"): Press a special key (e.g., "enter", "escape", "tab").
- complete(): If the current task or overall objective is clearly completed based on the screenshot.

Based on your analysis, provide your reasoning and the next action.
Respond with a JSON object containing two keys: "thinking" and "action".
"thinking" should be a brief explanation of your thought process.
"action" should be a string representing the browser command to execute.

Example:
{
  "thinking": "The user wants to search for 'ollama'. The search bar is element 3 and is currently empty. I should type 'ollama' into it.",
  "action": "type(\\"ollama\\", into=\\"search input with current value \\"Search text\\"\\")"
}
"""
        # Ensure the image path is valid and the image can be read
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
        except FileNotFoundError:
            print(f"Error: Image file not found at {image_path}")
            return {"thinking": "Error: Image file not found.", "action": ""}
        except Exception as e:
            print(f"Error reading image file {image_path}: {e}")
            return {"thinking": f"Error reading image: {e}", "action": ""}

        try:
            # Using ollama.chat for multimodal input with LLaVA
            # The 'content' combines the textual instruction and the image.
            # LLaVA models expect the image to be part of the prompt content.
            response = self.client.chat(
                model=model_name, # e.g., 'llava' or 'bakllava'
                messages=[
                    {
                        'role': 'system',
                        'content': system_prompt,
                    },
                    {
                        'role': 'user',
                        'content': f"Objective: {current_objective}\nCurrent Task: {current_task}\nAnalyze the screenshot and decide the next action.",
                        'images': [image_bytes] # Pass image bytes directly
                    }
                ],
                format="json" # Request JSON output if supported by the model/Ollama version for chat
            )

            # The response from client.chat is a dictionary, message content is under response['message']['content']
            raw_response_content = response.get('message', {}).get('content', '')
            if not raw_response_content:
                 return {"thinking": "Received empty content from Ollama.", "action": ""}

            parsed_output = self._parse_ollama_response(raw_response_content, ["thinking", "action"])
            if "error_parsing" in parsed_output:
                # Fallback: if JSON parsing fails, put the raw response in 'thinking'
                return {"thinking": f"Failed to parse LLaVA response as JSON: {raw_response_content}", "action": ""}
            return parsed_output

        except ollama.ResponseError as e:
            print(f"Ollama API error (analyze_and_decide with {model_name}): {e.status_code} - {e.error}")
            # If model not found, this is often a 404
            if e.status_code == 404:
                return {"thinking": f"Error: Model '{model_name}' not found in Ollama. Please ensure it's pulled and spelled correctly.", "action": ""}
            return {"thinking": f"Ollama API error: {e.error}", "action": ""}
        except requests.exceptions.ConnectionError:
            print(f"Error: Could not connect to Ollama at {self.client._client.host}.")
            return {"thinking": "Error: Connection to Ollama failed.", "action": ""}
        except Exception as e:
            print(f"An unexpected error occurred in analyze_and_decide with {model_name}: {e}")
            return {"thinking": f"Unexpected error: {e}", "action": ""}


    def generate_steps_for_todo(self, task_description: str, model_name: str = "llama3.2") -> list[str]:
        """Generates a list of steps for a given task using Ollama."""
        system_prompt = f"""You are a planning assistant. Given a user's objective, break it down into a sequence of actionable steps.
The user's objective is: "{task_description}"
Provide a list of concise steps to achieve this objective.
Respond with a JSON array of strings, where each string is a step.
Example:
["Navigate to google.com", "Search for 'Ollama installation'", "Read the installation guide", "Install Ollama"]
"""
        try:
            # Using ollama.generate for text-only models like llama3.2
            response = self.client.generate(
                model=model_name,
                prompt=f"Objective: {task_description}", # The user's raw request is the primary prompt here
                system=system_prompt, # System prompt guides the model's behavior and output format
                format="json" # Request JSON output
            )
            # response['response'] contains the string, which should be JSON formatted
            raw_response_content = response.get('response', '')
            if not raw_response_content:
                return ["Error: Received empty response from Ollama for step generation."]

            # We expect a list of strings, so _parse_ollama_response needs to handle this.
            # Let's assume _parse_ollama_response is adapted or we parse directly.
            try:
                # Attempt to parse the entire response as a JSON list directly
                steps = json.loads(raw_response_content)
                if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
                    return steps
                # If it's a dict with a "steps" key (due to _parse_ollama_response heuristic)
                elif isinstance(steps, dict) and "steps" in steps and isinstance(steps["steps"], list):
                    return steps["steps"]
                else:
                    # Fallback if parsing gives unexpected type, but it's a string
                    if isinstance(raw_response_content, str) and raw_response_content.strip():
                        # If the model didn't produce a list, wrap its output as a single step
                         return [f"Could not parse steps as list. Raw output: {raw_response_content}"]
                    return ["Error: Could not parse steps from Ollama response or response was not a list."]

            except json.JSONDecodeError:
                 # If JSON parsing fails, return the raw response as a single step (or an error message)
                if isinstance(raw_response_content, str) and raw_response_content.strip():
                    return [f"Failed to parse steps as JSON. Raw output: {raw_response_content}"]
                return ["Error: Failed to parse steps as JSON from Ollama response."]

        except ollama.ResponseError as e:
            print(f"Ollama API error (generate_steps_for_todo with {model_name}): {e.status_code} - {e.error}")
            if e.status_code == 404:
                return [f"Error: Model '{model_name}' not found in Ollama."]
            return [f"Error: Ollama API error - {e.error}"]
        except requests.exceptions.ConnectionError:
            print(f"Error: Could not connect to Ollama at {self.client._client.host}.")
            return ["Error: Connection to Ollama failed."]
        except Exception as e:
            print(f"An unexpected error occurred in generate_steps_for_todo with {model_name}: {e}")
            return [f"Error: Unexpected error - {str(e)}"]


    def analyze_state_vision(self, image_path: str, previous_task: str, current_task: str, next_task: str, objective: str, model_name: str = "llava") -> dict:
        """Analyzes the current state using an image and task context with a LLaVA model."""
        system_prompt = """You are an AI assistant evaluating the outcome of a web automation action.
You will receive a screenshot of the web page *after* an action was performed.
You will also get the overall objective, the specific task that was just attempted, and context about previous/next tasks.
Your goal is to determine if the attempted task was completed, if the overall objective is met, or if an error occurred.

Respond with a JSON object containing the following keys:
- "summary": A brief summary of your analysis of the current state based on the image and task.
- "error": A string describing any error detected that prevented task completion, or null/empty if no error.
- "task_completed": Boolean, true if the current task is verifiably completed based on the screenshot, false otherwise.
- "objective_completed": Boolean, true if the overall objective is verifiably completed, false otherwise.

Example:
{
  "summary": "The search results for 'Ollama' are displayed. The task 'Search for Ollama' is complete.",
  "error": null,
  "task_completed": true,
  "objective_completed": false
}
"""
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
        except FileNotFoundError:
            return {"summary": "Error: Image file not found.", "error": "Image file not found", "task_completed": False, "objective_completed": False}
        except Exception as e:
            return {"summary": f"Error reading image: {e}", "error": f"Error reading image: {e}", "task_completed": False, "objective_completed": False}

        try:
            response = self.client.chat(
                model=model_name, # e.g., 'llava'
                messages=[
                    {
                        'role': 'system',
                        'content': system_prompt,
                    },
                    {
                        'role': 'user',
                        'content': f"Objective: {objective}\nAttempted Task: {current_task}\nPrevious Task: {previous_task}\nNext Task: {next_task}\nAnalyze the screenshot to evaluate the outcome of the attempted task.",
                        'images': [image_bytes]
                    }
                ],
                format="json"
            )
            raw_response_content = response.get('message', {}).get('content', '')
            if not raw_response_content:
                return {"summary": "Received empty content from Ollama for state analysis.", "error": "Empty response", "task_completed": False, "objective_completed": False}

            parsed_output = self._parse_ollama_response(raw_response_content, ["summary", "error", "task_completed", "objective_completed"])

            if "error_parsing" in parsed_output:
                return {"summary": f"Failed to parse LLaVA response as JSON: {raw_response_content}", "error": "JSON parsing failed", "task_completed": False, "objective_completed": False}

            # Ensure boolean conversion for completion flags
            parsed_output["task_completed"] = str(parsed_output.get("task_completed", False)).lower() == 'true'
            parsed_output["objective_completed"] = str(parsed_output.get("objective_completed", False)).lower() == 'true'
            # Ensure error is a string or None
            parsed_output["error"] = parsed_output.get("error") if parsed_output.get("error") else None


            return parsed_output

        except ollama.ResponseError as e:
            print(f"Ollama API error (analyze_state_vision with {model_name}): {e.status_code} - {e.error}")
            if e.status_code == 404:
                 summary = f"Error: Model '{model_name}' not found in Ollama."
                 error_msg = summary
            else:
                summary = f"Ollama API error: {e.error}"
                error_msg = summary
            return {"summary": summary, "error": error_msg, "task_completed": False, "objective_completed": False}
        except requests.exceptions.ConnectionError:
            summary = "Error: Connection to Ollama failed."
            return {"summary": summary, "error": summary, "task_completed": False, "objective_completed": False}
        except Exception as e:
            summary = f"Unexpected error: {e}"
            print(f"An unexpected error occurred in analyze_state_vision with {model_name}: {e}")
            return {"summary": summary, "error": summary, "task_completed": False, "objective_completed": False}


if __name__ == '__main__':
    # Example Usage (requires Ollama to be running with llama3.2 model)
    client = OllamaClient()

    print("Listing available models:")
    models = client.list_models()
    if models:
        for model in models:
            print(f"- {model['name']}")
    else:
        print("No models found or Ollama not running.")

    print("\nAttempting to generate text with llama3.2 (if available):")
    # Check if llama3.2 is available
    target_model = "llama3.2" # Define the target model name

    if client.is_model_available(target_model):
        print(f"Model '{target_model}' is available locally.")
        prompt_text = "Why is the sky blue?"
        generated_output = client.generate_text(prompt_text, model_name=target_model)
        print(f"\nPrompt: {prompt_text}")
        print(f"Generated text: {generated_output}")
    elif models: # Ollama is running but model not found
        print(f"Model '{target_model}' not found locally.")
        print(f"Attempting to pull '{target_model}'...")
        success, message = client.pull_model(target_model)
        print(message)
        if success and client.is_model_available(target_model):
            print(f"Model '{target_model}' now available. Retrying generation...")
            prompt_text = "Why is the sky blue?"
            generated_output = client.generate_text(prompt_text, model_name=target_model)
            print(f"\nPrompt: {prompt_text}")
            print(f"Generated text: {generated_output}")
        elif success: # Pull success but not found, or already existed
             print(f"Model '{target_model}' might be available now or already existed. Please check Ollama status or try generation again.")
        else:
            print(f"Could not use model '{target_model}'.")
    else: # No models and Ollama not running
        print(f"Cannot check or pull '{target_model}' as Ollama connection failed earlier or no models returned.")

    # Example Usage (requires Ollama to be running with llama3.2 and a LLaVA model like 'llava')
    client = OllamaClient()
    target_model_text = "llama3.2"
    target_model_vision = "llava" # Or your specific LLaVA model name

    print("Listing available models:")
    models = client.list_models()
    if models:
        for model in models:
            print(f"- {model['name']}")
    else:
        print("No models found or Ollama not running.")

    # Test generate_steps_for_todo
    print(f"\n--- Testing generate_steps_for_todo with {target_model_text} ---")
    if client.is_model_available(target_model_text):
        steps_task = "Plan a trip to Paris"
        steps = client.generate_steps_for_todo(steps_task, model_name=target_model_text)
        print(f"Generated steps for '{steps_task}':")
        for i, step in enumerate(steps):
            print(f"{i+1}. {step}")
    else:
        print(f"Model {target_model_text} not available. Skipping generate_steps_for_todo test.")

    # For vision models, we need a dummy image. Create one if it doesn't exist.
    dummy_image_path = "dummy_screenshot.png"
    try:
        from PIL import Image
        if not subprocess.os.path.exists(dummy_image_path):
            img = Image.new('RGB', (600, 400), color = 'red')
            img.save(dummy_image_path)
            print(f"\nCreated dummy image: {dummy_image_path}")
    except ImportError:
        print("\nPIL (Pillow) not installed, cannot create dummy image for vision tests. `pip install Pillow`")
    except Exception as e:
        print(f"\nError creating dummy image: {e}")


    if subprocess.os.path.exists(dummy_image_path):
        print(f"\n--- Testing analyze_and_decide with {target_model_vision} ---")
        if client.is_model_available(target_model_vision):
            analysis_decision = client.analyze_and_decide(dummy_image_path, "Click the login button", "Log into the website", model_name=target_model_vision)
            print(f"Analysis and Decision:\nThinking: {analysis_decision.get('thinking')}\nAction: {analysis_decision.get('action')}")
        else:
            print(f"Model {target_model_vision} not available. Skipping analyze_and_decide test.")

        print(f"\n--- Testing analyze_state_vision with {target_model_vision} ---")
        if client.is_model_available(target_model_vision):
            state_analysis = client.analyze_state_vision(dummy_image_path, "Typed username", "Submit login form", "Verify login success", "Log into the website", model_name=target_model_vision)
            print(f"State Analysis:\nSummary: {state_analysis.get('summary')}\nError: {state_analysis.get('error')}\nTask Completed: {state_analysis.get('task_completed')}\nObjective Completed: {state_analysis.get('objective_completed')}")
        else:
            print(f"Model {target_model_vision} not available. Skipping analyze_state_vision test.")
    else:
        print(f"\nSkipping vision model tests as dummy image '{dummy_image_path}' could not be created/found.")
