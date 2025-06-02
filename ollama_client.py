import requests
import json
import base64
import os

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434/api"):
        self.base_url = base_url
        # No API key needed for local Ollama instances typically

    def generate_completion(self, prompt: str, model_name: str = "llama2", image_base64: str = None, options: dict = None):
        """
        Generates a completion using the Ollama API (/api/generate).

        Args:
            prompt: The text prompt for the model.
            model_name: The name of the Ollama model to use (defaults to "llama2").
            image_base64: Optional base64 encoded image for multimodal models.
            options: Optional dictionary of Ollama options (e.g., temperature).

        Returns:
            The text response from the model, or None if an error occurs.
        """
        try:
            headers = {
                "Content-Type": "application/json"
            }

            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False  # Get the full response at once
            }

            if image_base64:
                payload["images"] = [image_base64]

            if options:
                payload["options"] = options

            response = requests.post(
                f"{self.base_url}/generate", # Corrected endpoint
                headers=headers,
                json=payload,
                timeout=60 # Increased timeout for potentially long generations
            )

            response.raise_for_status() # Raise an exception for HTTP errors

            result = response.json()

            # The actual response text is in the 'response' field for stream=False
            return result.get("response")

        except requests.exceptions.Timeout:
            print(f"API request timed out in generate_completion for model {model_name}.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"API request failed in generate_completion (model: {model_name}): {str(e)}. Response text: {e.response.text if e.response else 'N/A'}")
            return None
        except Exception as e:
            print(f"Error in generate_completion (model: {model_name}): {str(e)}")
            return None

    def list_models(self):
        """
        Fetches the list of available models from the Ollama API.
        Corresponds to Ollama's /api/tags endpoint.
        """
        try:
            response = requests.get(
                f"{self.base_url}/tags",
                timeout=10
            )
            response.raise_for_status() # Raise an exception for HTTP errors

            models_data = response.json()
            # The response is expected to be like: {"models": [{"name": "model1:latest", ...}, ...]}
            if "models" in models_data and isinstance(models_data["models"], list):
                return [model.get("name") for model in models_data["models"] if model.get("name")]
            else:
                print(f"Unexpected response format from /api/tags: {models_data}")
                return []

        except requests.exceptions.Timeout:
            print("API request timed out while listing models.")
            return []
        except requests.exceptions.RequestException as e:
            print(f"API request failed while listing models: {str(e)}. Response text: {e.response.text if e.response else 'N/A'}")
            return []
        except Exception as e:
            print(f"Error listing models: {str(e)}")
            return []

    # --- Methods below are from the original MistralClient and need significant adaptation for Ollama ---
    # For now, they are commented out or simplified as they require different prompting and response parsing.

    # def analyze_and_decide(self, image_base64, user_objective, model_name: str, current_context=None):
    #     """
    #     Placeholder: This method needs to be adapted for Ollama's capabilities,
    #     potentially using the /api/chat endpoint and specific prompt engineering.
    #     """
    #     prompt = f"Objective: {user_objective}\nContext: {current_context}\nAnalyze the image and decide next action."
    #     # This is a simplistic adaptation. Real implementation would need JSON mode if supported,
    #     # or careful prompt engineering to get structured output.
    #     response_text = self.generate_completion(prompt, model_name, image_base64=image_base64)
    #     if response_text:
    #         # Attempt to parse or structure the response_text if needed.
    #         # For now, returning a simplified dict.
    #         return {"thinking": "Analysis based on Ollama response.", "action": response_text[:100]} # Example
    #     return {"thinking": "Failed to get response from Ollama.", "action": "ERROR"}

    # def generate_steps_for_todo(self, user_prompt: str, model_name: str) -> list[str]:
    #     """
    #     Placeholder: This method needs to be adapted for Ollama.
    #     Prompt engineering will be key to get a list of steps.
    #     """
    #     # Example prompt - this would need refinement
    #     ollama_prompt = f"Given the objective: '{user_prompt}', break it down into a numbered list of actionable steps for web automation. Output only the list."
    #     response_text = self.generate_completion(ollama_prompt, model_name)

    #     if response_text:
    #         steps = [step.strip() for step in response_text.splitlines() if step.strip()]
    #         return steps
    #     return []

    # def analyze_state_vision(self, image_base64: str, current_task: str, objective: str, model_name: str) -> dict:
    #     """
    #     Placeholder: This method needs to be adapted for Ollama,
    #     focusing on multimodal models and structured JSON output if possible.
    #     """
    #     # Example prompt - this would need significant refinement and potentially JSON mode if the model supports it.
    #     ollama_prompt = f"Image analysis needed. Current task: '{current_task}'. Overall objective: '{objective}'. Describe errors, task completion, objective completion, and summary based on the image."
    #     response_text = self.generate_completion(ollama_prompt, model_name, image_base64=image_base64)

    #     if response_text:
    #         # This is a very basic parsing attempt. True JSON output would be better.
    #         return {
    #             "error": "Model output: " + response_text[:50], # Placeholder
    #             "task_completed": "complete" in response_text.lower(), # Simplistic
    #             "objective_completed": "objective achieved" in response_text.lower(), # Simplistic
    #             "summary": response_text
    #         }
    #     return {
    #         "error": "Failed to get response from Ollama.",
    #         "task_completed": False,
    #         "objective_completed": False,
    #         "summary": "Could not obtain analysis."
    #     }

    # --- Keeping the original Mistral methods commented out for reference ---
    # def generate_steps_for_todo(self, user_prompt: str, model_name: str) -> list[str]:
    #     """
    #     Generates a list of actionable steps for web automation based on a user prompt.

    #     Args:
    #         user_prompt: The high-level objective from the user.
    #         model_name: The Mistral model to use for generation.

    #     Returns:
    #         A list of strings, where each string is a step. Returns an empty list if parsing fails.
    #     """
    #     system_prompt = """You are an expert planning agent... (original prompt)"""
    #     try:
    #         headers = {
    #             "Authorization": f"Bearer {self.api_key}", # Needs removal for Ollama
    #             "Content-Type": "application/json"
    #         }
    #         # ... rest of original Mistral implementation
    #     except Exception as e:
    #         print(f"Failed to generate steps: {str(e)}")
    #         return []

    # def analyze_state_vision(self, image_base64: str, current_task: str, objective: str, model_name: str) -> dict:
    #     """
    #     Analyzes a screenshot (image_base64) ... (original docstring)
    #     """
    #     system_prompt = """You are an expert web page analysis agent... (original prompt)"""
    #     # ... rest of original Mistral implementation
    #     try:
    #         headers = {
    #             "Authorization": f"Bearer {self.api_key}", # Needs removal for Ollama
    #             "Content-Type": "application/json"
    #         }
    #         # ... rest of original Mistral implementation
    #     except Exception as e:
    #         print(f"Failed to analyze state with vision: {str(e)}")
    #         # return default_error_response (original had this)
    #         return { "error": str(e), "task_completed": False, "objective_completed": False, "summary": "Error during analysis."}
