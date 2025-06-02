import json
from typing import List, Dict, Optional
from llama_index.llms.llama_cpp import LlamaCPP
from llama_index.core.llms import CompletionResponse
from llama_index.core.schema import ImageDocument
import base64
import os
import uuid # For unique temporary file names
import re

class LocalModelClient:
    def __init__(
        self,
        model_path: str, # This will be the main GGUF file path for qwen2.5vl
        clip_model_path: Optional[str] = None, # For Llava-like multi-modal models
        model_name: str = "qwen2.5vl", # For reference/logging
        temperature: float = 0.1,
        max_new_tokens: int = 2048, # Increased for potentially longer JSON outputs / thoughts
        context_window: int = 3900, # Should be appropriate for qwen2.5vl
        n_gpu_layers: int = -1, # Offload all possible layers to GPU
        verbose: bool = False # LlamaCPP verbose flag
    ):
        self.model_path = model_path
        self.model_name = model_name
        self.clip_model_path = clip_model_path
        self.is_multimodal = bool(clip_model_path) # Determine if configured for multi-modal

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Main GGUF model file not found at: {self.model_path}")
        if self.is_multimodal and self.clip_model_path and not os.path.exists(self.clip_model_path):
            raise FileNotFoundError(f"CLIP model file not found at: {self.clip_model_path}")

        try:
            llm_kwargs = {
                "model_path": self.model_path,
                "temperature": temperature,
                "max_new_tokens": max_new_tokens,
                "context_window": context_window,
                "generate_kwargs": {}, # Can be used for specific LlamaCPP generate params
                "model_kwargs": {"n_gpu_layers": n_gpu_layers},
                "verbose": verbose,
            }

            # Add clip_model_path only if model is multi-modal and path is provided
            # This is crucial for Llava-like models with LlamaCPP
            if self.is_multimodal and self.clip_model_path:
                llm_kwargs["clip_model_path"] = self.clip_model_path

            self.llm = LlamaCPP(**llm_kwargs)

            print(f"LocalModelClient initialized for model '{self.model_name}' from path '{self.model_path}'. Multi-modal: {self.is_multimodal}")

        except Exception as e:
            print(f"Error initializing LlamaCPP model from path {self.model_path}: {e}")
            raise RuntimeError(f"Failed to initialize LlamaCPP: {e}")

    def _parse_json_response(self, response_text: str, method_name: str) -> Dict:
        """
        Helper to parse JSON from LLM response text.
        Attempts to strip markdown code blocks if present.
        """
        try:
            # Remove potential markdown code block fences
            # Handles ```json ... ``` or just ``` ... ```
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = response_text.strip() # Assume the response is already a plain JSON string

            if not json_str:
                 raise json.JSONDecodeError("Response text is empty after stripping.", "", 0)

            data = json.loads(json_str)

            if method_name == "analyze_state_vision":
                for key in ["task_completed", "objective_completed"]:
                    if key in data: # Check if key exists before lowercasing
                        value = data[key]
                        if isinstance(value, str):
                            data[key] = value.lower() == 'true'
                        elif isinstance(value, bool):
                            data[key] = value # Already a boolean
                        else: # Handle unexpected types by defaulting to False
                            data[key] = False
            return data
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError in {method_name}: {e}. Response text: '{response_text[:300]}...'")
            error_payload = {
                "error_message": f"JSON parsing failed: {e}",
                "raw_response": response_text,
                "method": method_name
            }
            if method_name == "analyze_and_decide":
                return {"thinking": f"Error: Could not parse JSON. {error_payload['raw_response'][:100]}", "action": "", "error_details": error_payload}
            elif method_name == "analyze_state_vision":
                return {
                    "error": f"Could not parse JSON. {error_payload['raw_response'][:100]}",
                    "task_completed": False, "objective_completed": False,
                    "summary": "Failed to parse model output.", "error_details": error_payload
                }
            elif method_name == "generate_steps_for_todo": # Should return a list
                 return {"error": "json_parsing_error", "steps_error": error_payload }
            return {"error": "json_parsing_error", "details": error_payload}


    def generate_steps_for_todo(self, objective: str) -> List[str]:
        """Generates a list of actionable web automation steps for a given objective."""
        system_prompt = """You are an expert planning agent for web automation.
Given a user's high-level objective, break it down into a sequence of specific, actionable sub-tasks.
Each step should be a concrete action a web automation script can perform or a verification point.
Respond ONLY with a valid JSON array of strings, where each string is a step. Do not add any introductory text, explanations, or markdown formatting around the JSON.

Example for User Objective: "Order a pizza online"
Example JSON Response:
["Navigate to a pizza delivery website (e.g., dominos.com)", "Select pizza type and toppings", "Add to cart", "Proceed to checkout", "Enter delivery address and payment information", "Confirm order"]
"""
        full_prompt = f"{system_prompt}\n\nUser Objective: {objective}\n\nJSON Response:"

        try:
            response = self.llm.complete(full_prompt)
            parsed_output = self._parse_json_response(response.text, "generate_steps_for_todo")

            if isinstance(parsed_output, list):
                return parsed_output
            elif isinstance(parsed_output, dict) and "steps" in parsed_output and isinstance(parsed_output["steps"], list):
                 return parsed_output["steps"]
            elif isinstance(parsed_output, dict) and "error" in parsed_output: # Error from _parse_json_response
                return [f"Error parsing steps: {parsed_output.get('steps_error', {}).get('raw_response', '')[:100]}"]
            else: # Fallback if parsing yields unexpected dict or other types
                 # Attempt to split by newline if model didn't follow JSON format
                steps_text = response.text.strip()
                if steps_text.startswith("[") and steps_text.endswith("]"): # Looks like a list string but failed parse
                    return [f"Could not parse JSON list: {steps_text[:150]}"]

                steps = [s.strip().lstrip('-').strip() for s in steps_text.splitlines() if s.strip().lstrip('-').strip()]
                return steps if steps else [f"Could not generate or parse steps. Raw: {steps_text[:150]}"]
        except Exception as e:
            print(f"Error in generate_steps_for_todo: {e}")
            return [f"Error generating steps: {str(e)}"]

    def _create_temporary_image_file(self, image_base64: str) -> Optional[str]:
        """Creates a temporary image file from a base64 string."""
        if not image_base64:
            return None
        try:
            image_data = base64.b64decode(image_base64)
            temp_dir = "temp_images" # Consider using tempfile module for more robust temp handling
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            # Generate a unique filename
            img_filename = f"{uuid.uuid4()}.png"
            img_path = os.path.join(temp_dir, img_filename)

            with open(img_path, "wb") as f:
                f.write(image_data)
            return img_path
        except Exception as e:
            print(f"Error creating temporary image file: {e}")
            return None

    def _cleanup_temporary_image_file(self, img_path: Optional[str]):
        """Cleans up (deletes) a temporary image file."""
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception as e:
                print(f"Error cleaning up temporary image file {img_path}: {e}")


    def analyze_and_decide(self, image_base64: str, user_objective: str, current_task: Optional[str] = None) -> Dict:
        if not self.is_multimodal:
            return {"thinking": "Error: Client not configured for multi-modal analysis (CLIP model path missing).", "action": ""}

        system_prompt = """You are an expert web automation assistant. Analyze the provided webpage screenshot (image) and the user's current objective and task.
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
}"""
        text_prompt = f"User Objective: {user_objective}\nCurrent Task: {current_task if current_task else 'N/A'}\n\nJSON Response:"

        img_path = None
        try:
            img_path = self._create_temporary_image_file(image_base64)
            if not img_path:
                return {"thinking": "Error: Could not process input image.", "action": ""}

            image_doc = ImageDocument(image_path=img_path)

            # LlamaCPP's complete method might take image_documents.
            # The prompt structure for multi-modal with LlamaCPP can vary.
            # Some GGUF versions might expect image marker in prompt like "<image>".
            # Here, using `image_documents` as it's a LlamaIndex standard.
            # Note: LlamaCPP's chat mode is often better for multi-modal with Llava.
            # If .complete doesn't work well, .chat might be an alternative if llama-index-llms-llama-cpp supports it for multimodal.
            # For now, assuming .complete with image_documents.

            # Constructing a prompt that LlamaCPP with Llava typically expects:
            # USER: <image>\n{text_prompt}
            # ASSISTANT: {json_response}
            # However, LlamaIndex's OllamaMultiModal usually handles this internally.
            # For LlamaCPP, we might need to pass the system prompt differently or combine.
            # Let's try passing the system prompt via generate_kwargs if that's how LlamaCPP integration handles it,
            # or prepend it to the user prompt. Given LlamaCPP, prepending is more common.

            full_prompt_for_llamacpp = f"{system_prompt}\n\nUSER: <image>\n{text_prompt}\nASSISTANT:"

            response = self.llm.complete(full_prompt_for_llamacpp, image_documents=[image_doc])
            return self._parse_json_response(response.text, "analyze_and_decide")
        except Exception as e:
            print(f"Error in analyze_and_decide: {e}")
            return {"thinking": f"Error during analysis: {e}", "action": ""}
        finally:
            self._cleanup_temporary_image_file(img_path)


    def analyze_state_vision(self, image_base64: str, current_task: str, objective: str) -> Dict:
        if not self.is_multimodal:
            return {
                "error": "Client not configured for multi-modal analysis (CLIP model path missing).",
                "task_completed": False, "objective_completed": False,
                "summary": "Multi-modal not configured."
            }

        system_prompt = """You are an expert web page analysis agent. Analyze the screenshot in context of the current task and overall objective.
Output ONLY a valid JSON object with keys: "summary" (string analysis), "error" (string or null), "task_completed" (boolean), "objective_completed" (boolean).

Example:
{
  "summary": "The user profile page is displayed, indicating successful login.",
  "error": null,
  "task_completed": true,
  "objective_completed": false
}"""
        text_prompt = f"Current Task: \"{current_task}\"\nOverall Objective: \"{objective}\"\n\nJSON Response:"

        img_path = None
        try:
            img_path = self._create_temporary_image_file(image_base64)
            if not img_path:
                 return {
                    "error": "Could not process input image for vision analysis.",
                    "task_completed": False, "objective_completed": False,
                    "summary": "Image processing failed."
                }
            image_doc = ImageDocument(image_path=img_path)

            full_prompt_for_llamacpp = f"{system_prompt}\n\nUSER: <image>\n{text_prompt}\nASSISTANT:"

            response = self.llm.complete(full_prompt_for_llamacpp, image_documents=[image_doc])
            return self._parse_json_response(response.text, "analyze_state_vision")
        except Exception as e:
            print(f"Error in analyze_state_vision: {e}")
            return {
                "error": f"Error during vision analysis: {e}",
                "task_completed": False, "objective_completed": False, "summary": "Analysis failed."
            }
        finally:
            self._cleanup_temporary_image_file(img_path)

```
