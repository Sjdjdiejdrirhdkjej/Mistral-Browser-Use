import subprocess
import json
import os
import base64
import re
import uuid # For temporary file names

from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.multi_modal_llms.ollama import OllamaMultiModal
from llama_index.core.llms import CompletionResponse # Corrected: MultiModalCompletionResponse is not standard for .complete() text output
# from llama_index.core.multi_modal_llms import MultiModalCompletionResponse # This was likely the source of error
# from llama_index.core.base.response.schema import ResponseType # Not directly used for now
from llama_index.core.schema import ImageDocument
# Import ChatMessage if using .chat() method and need to type hint its response
from llama_index.core.base.llms.types import ChatMessage

# Default Ollama base URL
OLLAMA_BASE_URL = "http://localhost:11434"
# Ensure qwen2.5vl is the primary model for all tasks by default with this client.
DEFAULT_QWEN_MODEL = "qwen2.5vl"

class LlamaIndexClient:
    def __init__(self,
                 model_name: str = DEFAULT_QWEN_MODEL, # Single model_name for qwen2.5vl
                 # ollama_base_url: str = OLLAMA_BASE_URL, # Removed from constructor
                 request_timeout: float = 120.0):

        self.model_name = model_name # This will be "qwen2.5vl"
        self.ollama_base_url = OLLAMA_BASE_URL # Hardcoded to default
        self.request_timeout = request_timeout

        try:
            # Initialize LLM for text tasks. qwen2.5vl is multimodal, so it can handle text.
            # Forcing qwen2.5vl for text generation tasks as well for consistency.
            self.llm = Ollama(
                model=self.model_name,
                base_url=self.ollama_base_url, # Explicitly set to default
                request_timeout=self.request_timeout,
                temperature=0.1,
                format="json" # Request JSON output by default for text generation
            )

            # Initialize MultiModal LLM for vision tasks, using the same qwen2.5vl model
            self.multi_modal_llm = OllamaMultiModal(
                model=self.model_name,
                base_url=self.ollama_base_url, # Explicitly set to default
                request_timeout=self.request_timeout,
                temperature=0.1,
                format="json" # Request JSON output by default for multimodal tasks
            )

            print(f"LlamaIndexClient initialized with model: '{self.model_name}' at {self.ollama_base_url} for both text and vision tasks.")

        except Exception as e:
            print(f"Error initializing LlamaIndexClient with model '{self.model_name}': {e}")
            self.llm = None
            self.multi_modal_llm = None
            raise RuntimeError(f"Failed to initialize LlamaIndex LLMs for model '{self.model_name}': {e}")


    def is_model_available(self, model_name: str) -> bool:
        """Checks if a specific model is available locally using 'ollama list'."""
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print(f"Error running 'ollama list': {result.stderr}")
                return False
            # Output of 'ollama list' is like:
            # NAME                            ID              SIZE    MODIFIED
            # llama3.2:latest                 abcdef123456    4.7 GB  1 week ago
            # qwen2.5vl:latest                fedcba654321    1.5 GB  2 weeks ago
            return model_name in result.stdout
        except FileNotFoundError:
            print("Error: 'ollama' command not found. Please ensure Ollama is installed and in PATH.")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while checking model availability for {model_name}: {e}")
            return False

    def pull_model(self, model_name: str) -> tuple[bool, str]:
        """Pulls a model using 'ollama pull <model_name>'."""
        try:
            print(f"Attempting to pull model: {model_name} via LlamaIndexClient...")
            # Stream output for better UX if this were a long process shown in UI
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding='utf-8'
            )

            stdout_lines = []
            stderr_lines = []

            # Non-blocking read is complex with Popen. For simplicity, using communicate here.
            # For real-time streaming in a UI, one would use select or threads.
            stdout, stderr = process.communicate(timeout=300) # 5-minute timeout for pull

            if process.returncode == 0:
                if "already exists" in stderr.lower() or "already exists" in stdout.lower():
                    msg = f"Model '{model_name}' already exists locally."
                    print(msg)
                    return True, msg
                msg = f"Successfully pulled model '{model_name}'. Output: {stdout}"
                print(msg)
                return True, msg
            else:
                error_message = f"Failed to pull model '{model_name}'. Code: {process.returncode}. Error: {stderr.strip()}. Output: {stdout.strip()}"
                print(error_message)
                return False, error_message
        except FileNotFoundError:
            error_message = "Error: 'ollama' command not found. Please ensure Ollama is installed and in your PATH."
            print(error_message)
            return False, error_message
        except subprocess.TimeoutExpired:
            error_message = f"Timeout while pulling model '{model_name}'. It might still be downloading in the background."
            print(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"An unexpected error occurred while pulling model '{model_name}': {e}"
            print(error_message)
            return False, error_message

    def _parse_json_from_response(self, response_text: str, context: str = "") -> dict:
        """Helper to parse JSON from LLM response text."""
        try:
            # Try to find JSON block, assuming it might be wrapped in markdown
            match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                # Fallback: assume the entire response is JSON or a JSON-like object
                # This is common if the model is specifically instructed for JSON output
                # and `format="json"` is used with Ollama (though LlamaIndex handles this internally).
                json_str = response_text

            # Further cleanup: remove leading/trailing whitespace and newlines from the extracted string
            json_str = json_str.strip()

            parsed = json.loads(json_str)
            if not isinstance(parsed, dict): # Ensure it's a dictionary
                raise json.JSONDecodeError("Parsed content is not a dictionary.", json_str, 0)
            return parsed
        except json.JSONDecodeError as e:
            print(f"JSON Parsing Error ({context}): {e}. Raw response: '{response_text[:500]}...'")
            return {"error": "json_parsing_error", "message": str(e), "context": context, "raw_response": response_text}


    def generate_steps_for_todo(self, objective: str) -> list[str]:
        """Generates a list of actionable web automation steps for a given objective."""
        if not self.llm: # Using self.llm as qwen2.5vl can handle text too
            return ["Error: LLM (qwen2.5vl for text) not initialized."]

        # Refined system prompt for qwen2.5vl for step generation
        system_prompt = """You are an expert planning agent for web automation.
Given a user's high-level objective, break it down into a sequence of specific, actionable sub-tasks.
Each step should be a concrete action a web automation script can perform or a verification point.
Present the steps as a JSON array of strings. Each string in the array is one step.
Ensure your entire response is ONLY this JSON array. Do not add any introductory text, explanations, or markdown formatting around the JSON.

Example User Objective: Sign up for a newsletter on example.com
Example JSON Response:
["Navigate to https://example.com", "Find the newsletter signup form", "Enter email address into the email input field", "Click the 'Subscribe' button", "Verify subscription confirmation message"]
"""
        # User prompt for the LLM
        user_prompt = f"User Objective: {objective}"

        try:
            # Using the chat endpoint for more structured interaction.
            # self.llm is already configured with format="json".
            response = self.llm.chat(messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])

            response_text = response.message.content.strip()

            # Attempt to parse the response as a JSON list of strings
            try:
                # _parse_json_from_response might return a dict with "error" on failure
                # For this method, we strictly expect a list or a dict containing a list under "steps".
                parsed_data_wrapper = self._parse_json_from_response(response_text, "generate_steps_for_todo")

                if "error_parsing" in parsed_data_wrapper :
                    raw_resp = parsed_data_wrapper.get('raw_response', response_text)
                    print(f"generate_steps_for_todo: JSON parsing failed. Raw: {raw_resp[:200]}")
                    # Fallback: if not JSON, try splitting by newline (less reliable)
                    if "\n" in raw_resp:
                        steps = [s.strip().lstrip('- ').rstrip(',') for s in raw_resp.split('\n') if s.strip()]
                        steps = [s for s in steps if s and not s.lower().startswith(("here are", "sure, i can", "{", "```"))]
                        if steps: return steps
                    return [f"Error: Could not parse steps as JSON. Raw: {raw_resp[:200]}"]

                if isinstance(parsed_data_wrapper, list) and all(isinstance(step, str) for step in parsed_data_wrapper):
                    return parsed_data_wrapper
                elif isinstance(parsed_data_wrapper, dict) and "steps" in parsed_data_wrapper and isinstance(parsed_data_wrapper["steps"], list):
                    return parsed_data_wrapper["steps"]
                else:
                    print(f"generate_steps_for_todo: Parsed JSON is not a list of steps. Got: {parsed_data_wrapper}")
                    return [f"Error: AI response was valid JSON but not a list of steps. Output: {str(parsed_data_wrapper)[:200]}"]
            except json.JSONDecodeError: # Should be caught by _parse_json_from_response typically
                print(f"generate_steps_for_todo: Direct JSONDecodeError. Raw: {response_text[:200]}")
                if "\n" in response_text: # Fallback for direct decode error
                    steps = [s.strip().lstrip('- ').rstrip(',') for s in response_text.split('\n') if s.strip()]
                    steps = [s for s in steps if s and not s.lower().startswith(("here are", "sure, i can", "{", "```"))]
                    if steps: return steps
                return [f"Error: Could not parse steps. Raw: {response_text[:200]}"]

        except Exception as e:
            print(f"Error in generate_steps_for_todo with model {self.model_name}: {e}")
            return [f"Error generating steps: {str(e)}"]


    def analyze_and_decide(self, image_base64: str, user_objective: str, current_task_description: str) -> dict:
        """Analyzes screenshot and objective, returns JSON with 'thinking' and 'action'."""
        if not self.multi_modal_llm: # This should be initialized with qwen2.5vl
            return {"thinking": "Error: Multi-modal LLM (qwen2.5vl) not initialized.", "action": ""}

        # Refined system prompt for qwen2.5vl for analyze_and_decide
        system_prompt = """You are an expert web automation assistant.
Analyze the provided webpage screenshot (image) and the user's current objective and task.
Your goal is to determine the single next browser action to perform.
Available actions are:
- click(element_index): Click on the element with the given index. Element indexes are visible in the screenshot.
- type("text_to_type", into="element_description_or_index"): Type the specified text into the described element (e.g., 'search input with current value "Search text"').
- navigate_to("url_string"): Navigate to the given URL.
- press_key("key_name"): Press a special key (e.g., "enter", "escape", "tab").
- complete(): If the current task or overall objective is clearly completed based on the screenshot.

Respond ONLY with a single valid JSON object containing two keys: "thinking" and "action".
"thinking" should be a brief explanation of your thought process in analyzing the image and task.
"action" should be a string representing exactly one of the available browser commands.
Do not include any markdown formatting, explanations, or text outside the JSON object.

Example:
{
  "thinking": "The user wants to search for 'Ollama'. The search bar is element 3 and is currently empty. I should type 'ollama' into it.",
  "action": "type(\\"ollama\\", into=\\"search input with current value \\"Search text\\"\\")"
}
"""
        # User prompt combining objective and task for the multimodal LLM
        text_prompt = f"Current Objective: {user_objective}\nCurrent Task: {current_task_description}\nBased on the provided image, what is the next browser action to perform?"

        try:
            image_doc = ImageDocument(image=image_base64) # Pass base64 string directly

            # Using multi_modal_llm.chat for potentially better structured output with system/user roles
            # self.multi_modal_llm is already configured with format="json"
            # The response from .chat() is typically a ChatResponse object,
            # and its message content is accessed via response.message.content
            chat_response = self.multi_modal_llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_prompt, "image_documents": [image_doc]} # LlamaIndex standard for OllamaMultiModal chat
                ]
            )

            response_text = chat_response.message.content.strip()
            parsed_output = self._parse_json_from_response(response_text, "analyze_and_decide")

            if "error_parsing" in parsed_output: # Check if parsing helper returned an error structure
                return {"thinking": f"Error parsing decision: {parsed_output.get('raw_response', response_text)}", "action": ""}

            thinking = parsed_output.get("thinking", "No thinking provided by AI.")
            action = parsed_output.get("action", "")
            if not action: # If action is empty after successful parse
                 thinking += " (AI returned empty action)"
            return {"thinking": thinking, "action": action}

        except Exception as e:
            print(f"Error in analyze_and_decide with model {self.model_name}: {e}")
            return {"thinking": f"Error in analyze_and_decide: {str(e)}", "action": ""}


    def analyze_state_vision(self, image_base64: str, current_task: str, objective: str) -> dict:
        """Analyzes screenshot post-action, returns JSON with 'error', 'task_completed', 'objective_completed', 'summary'."""
        if not self.multi_modal_llm: # This should be initialized with qwen2.5vl
            return {"summary": "Error: Multi-modal LLM (qwen2.5vl) not initialized.", "error": "LLM not initialized", "task_completed": False, "objective_completed": False}

        # Refined system prompt for qwen2.5vl for analyze_state_vision
        system_prompt = """You are an expert web page analysis agent.
Analyze the provided screenshot (image) in the context of the current web automation task and the user's overall objective.
Determine if the attempted task was completed, if the overall objective has now been met, or if an error is visible or implied by the state.
Respond ONLY with a single valid JSON object containing the following keys:
- "summary": A brief text summary of your analysis of the current page state related to the task and objective.
- "error": A string describing any error detected that likely prevented task completion or indicates a problem. If no error, this should be null.
- "task_completed": A boolean value (true or false) indicating if the current task is verifiably completed based on the screenshot.
- "objective_completed": A boolean value (true or false) indicating if the overall user objective is verifiably completed based on the screenshot.
Do not include any markdown formatting, explanations, or text outside the JSON object.

Example:
{
  "summary": "The user profile page is displayed, indicating successful login.",
  "error": null,
  "task_completed": true,
  "objective_completed": false
}
"""
        text_prompt = f"Overall Objective: {objective}\nAttempted Task: {current_task}\nBased on the provided image, evaluate the outcome of the attempted task."

        try:
            image_doc = ImageDocument(image=image_base64)

            # self.multi_modal_llm is already configured with format="json"
            # The response from .chat() is typically a ChatResponse object
            chat_response = self.multi_modal_llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_prompt, "image_documents": [image_doc]}
                ]
            )
            response_text = chat_response.message.content.strip()
            parsed_output = self._parse_json_from_response(response_text, "analyze_state_vision")

            if "error_parsing" in parsed_output: # Check if parsing helper returned an error structure
                return {"summary": f"Error parsing state analysis: {parsed_output.get('raw_response', response_text)}", "error": "JSON parsing error", "task_completed": False, "objective_completed": False}

            summary = parsed_output.get("summary", "No summary provided by AI.")
            error = parsed_output.get("error")
            # Ensure boolean conversion for completion flags, handling actual booleans or strings "true"/"false"
            task_completed_val = parsed_output.get("task_completed", False)
            objective_completed_val = parsed_output.get("objective_completed", False)

            task_completed = task_completed_val if isinstance(task_completed_val, bool) else str(task_completed_val).lower() == 'true'
            objective_completed = objective_completed_val if isinstance(objective_completed_val, bool) else str(objective_completed_val).lower() == 'true'

            return {
                "summary": summary,
                "error": error if error and str(error).lower() != "null" else None,
                "task_completed": task_completed,
                "objective_completed": objective_completed
            }

        except Exception as e:
            print(f"Error in analyze_state_vision with model {self.model_name}: {e}")
            return {"summary": f"Error in analyze_state_vision: {str(e)}", "error": str(e), "task_completed": False, "objective_completed": False}

if __name__ == '__main__':
    print("LlamaIndexClient Main Execution (for basic testing)")

    # NOTE: This basic test requires 'ollama' service to be running and
    # the model (DEFAULT_QWEN_MODEL) to be available or pullable.

    # Create a dummy base64 image for testing vision capabilities
    # (A small 1x1 black pixel PNG)
    dummy_b64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    try:
        client = LlamaIndexClient(
            model_name=DEFAULT_QWEN_MODEL # Explicitly testing with qwen2.5vl
            # ollama_base_url is no longer passed
        )
        print("-" * 20)

        # Test model availability and pull (if needed)
        print(f"Checking availability of model: {client.model_name}")
        if not client.is_model_available(client.model_name):
            print(f"Model '{client.model_name}' not found. Attempting to pull...")
            success, message = client.pull_model(client.model_name)
            print(f"Pull result: {success} - {message}")
            if not success:
                print(f"Could not pull {client.model_name}. Tests might fail or be inaccurate.")
        else:
            print(f"Model '{client.model_name}' is available.")

        print("-" * 20)

        if client.llm: # llm is now also qwen2.5vl
            print("\nTesting generate_steps_for_todo...")
            todo_objective = "Create a new email account on gmail.com"
            steps = client.generate_steps_for_todo(todo_objective)
            print(f"Generated steps for '{todo_objective}':")
            for i, step in enumerate(steps):
                print(f"{i+1}. {step}")
            print("-" * 20)

        if client.multi_modal_llm: # multi_modal_llm is qwen2.5vl
            print("\nTesting analyze_and_decide...")
            decision = client.analyze_and_decide(
                image_base64=dummy_b64_image,
                user_objective="Find the search bar and search for 'LlamaIndex'",
                current_task_description="Identify the search bar on the page."
            )
            print(f"Decision: Thinking: {decision.get('thinking')}, Action: {decision.get('action')}")
            print("-" * 20)

            print("\nTesting analyze_state_vision...")
            state_analysis = client.analyze_state_vision(
                image_base64=dummy_b64_image,
                current_task="Clicked on the 'Login' button.",
                objective="Log into the website."
            )
            print(f"State Analysis: Summary: {state_analysis.get('summary')}, Error: {state_analysis.get('error')}, Task Completed: {state_analysis.get('task_completed')}, Objective Completed: {state_analysis.get('objective_completed')}")
            print("-" * 20)

    except RuntimeError as e:
        print(f"Could not run LlamaIndexClient tests: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during LlamaIndexClient main test: {e}")
