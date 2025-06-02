import requests # Kept for potential future use or consistency
from llama_index.llms.llama_cpp import LlamaCPP
from llama_index.core.llms import CompletionResponse, LLMMetadata # Adjust path if needed based on LlamaIndex version

# For older LlamaIndex versions, types might be under llama_index.core.llms.types
# from llama_index.core.llms.types import CompletionResponse, LLMMetadata

class LlamaIndexLocalClient:
    def __init__(self, model_path: str, temperature: float = 0.1, max_new_tokens: int = 2048, context_window: int = 3900, verbose: bool = True):
        """
        Initializes the LlamaIndexLocalClient with a LlamaCPP model.

        Args:
            model_path (str): Path to the GGUF model file.
            temperature (float): The temperature to use for sampling.
            max_new_tokens (int): The maximum number of tokens to generate.
            context_window (int): The context window for the model.
            verbose (bool): Whether to print verbose output from LlamaCPP.
        """
        self.model_path = model_path
        self.llm = None
        self.is_initialized = False

        try:
            # n_gpu_layers=-1 attempts to offload all layers to GPU.
            # Adjust if causing issues or for CPU-only inference (set to 0).
            self.llm = LlamaCPP(
                model_path=model_path,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                context_window=context_window,
                # model_kwargs are passed directly to the llama-cpp-python library
                model_kwargs={"n_gpu_layers": -1},
                verbose=verbose
            )
            self.is_initialized = True
            print(f"LlamaCPP model loaded successfully from: {model_path}")
        except Exception as e:
            # This can catch various errors: model file not found, invalid model,
            # issues with llama-cpp-python backend (e.g., compilation/linking errors if not properly installed)
            print(f"Error initializing LlamaCPP model from {model_path}: {e}")
            self.llm = None
            self.is_initialized = False

    def get_metadata(self) -> LLMMetadata:
        """
        Returns metadata about the loaded LLM.
        """
        if not self.is_initialized or not self.llm:
            # Return default or raise error
            print("Error: LlamaIndexLocalClient not initialized or model failed to load.")
            # Fallback to a default metadata structure if appropriate for your use case
            return LLMMetadata(context_window=0, num_output=0, model_name="Uninitialized")
        return self.llm.metadata

    def generate_completion(self, prompt: str, **kwargs) -> str:
        """
        Generates a completion for a given prompt.
        Additional kwargs are passed to the LlamaCPP.complete method.
        """
        if not self.is_initialized or not self.llm:
            return "Error: LlamaIndexLocalClient not initialized or model failed to load."

        try:
            response = self.llm.complete(prompt, **kwargs)
            return str(response)
        except Exception as e:
            print(f"Error during LlamaCPP completion: {e}")
            return f"Error during completion: {e}"

    def generate_steps_for_todo(self, task_description: str) -> list[str]:
        """
        Generates a list of actionable steps for a given task description.
        """
        if not self.is_initialized or not self.llm:
            return ["Error: LlamaIndexLocalClient not initialized or model failed to load."]

        prompt = f"""Prompt: You are a helpful assistant. Based on the following task, provide a concise list of actionable steps to complete it. Return ONLY the list of steps, each on a new line, starting with '- '. Do not add any preamble or explanation.
Task: {task_description}
Steps:
"""
        try:
            raw_response = self.llm.complete(prompt)
            response_text = str(raw_response)

            steps = []
            for line in response_text.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    steps.append(line[2:].strip()) # Remove "- " prefix
                elif line: # Include non-empty lines even if they don't start with "- " as a fallback
                    steps.append(line)

            if not steps and response_text: # If no "- " prefix was found but there is text
                steps.append(f"Raw model output (could not parse steps): {response_text}")

            return steps if steps else ["No steps generated or failed to parse."]
        except Exception as e:
            print(f"Error during LlamaCPP generate_steps_for_todo: {e}")
            return [f"Error generating steps: {e}"]

    def analyze_and_decide(self, analysis_prompt: str, items_to_consider: list[str] = None) -> str:
        """
        Performs analysis based on a prompt and a list of items.
        """
        if not self.is_initialized or not self.llm:
            return "Error: LlamaIndexLocalClient not initialized or model failed to load."

        items_str = ""
        if items_to_consider:
            items_str = "\n".join([f"- {item}" for item in items_to_consider])

        prompt = f"""Prompt: You are an analytical assistant. {analysis_prompt}.
Consider the following items if provided:
{items_str}

Provide your decision or analysis:
"""
        try:
            response = self.llm.complete(prompt)
            return str(response)
        except Exception as e:
            print(f"Error during LlamaCPP analyze_and_decide: {e}")
            return f"Error during analysis: {e}"

    def analyze_state_vision(self, prompt: str, image_url: str = None) -> str:
        """
        Placeholder for vision analysis. LlamaCPP with GGUF typically doesn't handle image URLs directly.
        This method would need a multimodal model (e.g., LLaVA via LlamaCPP or a different LlamaIndex setup).
        """
        if not self.is_initialized or not self.llm:
            return "Error: LlamaIndexLocalClient not initialized or model failed to load."

        if image_url:
            # If a multimodal model is loaded that *can* take an image_url (or path) via LlamaCPP,
            # the LlamaCPP class itself would need to support an 'image_url' or similar parameter in .complete()
            # or via its constructor for multimodal models.
            # Standard LlamaCPP is text-focused.
            # This is a simplified check; actual multimodal invocation is more complex.
            if hasattr(self.llm, "complete_with_image"): # Fictional method for illustration
                # return str(self.llm.complete_with_image(prompt, image_url=image_url))
                pass # Pass to the general message

            return "Vision analysis with image URLs is not directly supported by this basic LlamaCPP text client. A multimodal model and setup (e.g., LlamaMMMultiModal or specialized LlamaCPP arguments for vision) would be required."
        else:
            # If no image_url, treat as text-based analysis
            return self.generate_completion(prompt)

# Example Usage (for testing if run directly)
if __name__ == '__main__':
    # This example assumes you have a GGUF model file at the specified path.
    # Replace with the actual path to your model.
    # Make sure llama-cpp-python is correctly installed and compiled.
    # For GPU offloading, your llama-cpp-python build must support your GPU type (CUDA, Metal).

    # model_file_path = "/path/to/your/model.gguf" # E.g., /home/user/models/llama-2-7b-chat.Q4_K_M.gguf
    # print(f"Attempting to load model from: {model_file_path}")
    # client = LlamaIndexLocalClient(model_path=model_file_path)

    # if client.is_initialized:
    #     print("\nClient initialized successfully.")
    #     print("Model Metadata:", client.get_metadata())

    #     print("\nTesting generate_completion:")
    #     completion = client.generate_completion("Explain the importance of local LLMs in one sentence.")
    #     print("Completion:", completion)

    #     print("\nTesting generate_steps_for_todo:")
    #     steps = client.generate_steps_for_todo("Plan a one-day trip to San Francisco")
    #     print("Steps for SF trip:")
    #     for step in steps:
    #         print(f"- {step}")

    #     print("\nTesting analyze_and_decide:")
    #     analysis = client.analyze_and_decide(
    #         analysis_prompt="Should we invest in Project X?",
    #         items_to_consider=["High potential ROI", "Market competition is fierce", "Requires significant upfront capital"]
    #     )
    #     print("Analysis/Decision:", analysis)

    #     print("\nTesting analyze_state_vision (text-only, as image_url is None):")
    #     vision_text_analysis = client.analyze_state_vision(prompt="Describe a sunny day.")
    #     print("Text-based vision analysis:", vision_text_analysis)

    #     print("\nTesting analyze_state_vision (with dummy image_url to show message):")
    #     vision_image_analysis = client.analyze_state_vision(prompt="Describe this image.", image_url="dummy_path.jpg")
    #     print("Image-based vision analysis attempt:", vision_image_analysis)

    # else:
    #     print("\nClient failed to initialize. Check model path and llama-cpp-python installation.")
    pass # Keep the example code commented out for now
