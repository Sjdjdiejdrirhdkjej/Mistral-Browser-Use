import ollama
import json

class OllamaClient:
    def __init__(self, host='http://localhost:11434', model='llama2'):
        self.client = ollama.Client(host=host)
        self.model = model

    def analyze_and_decide(self, user_objective, current_context=None):
        """Analyze user objective and decide on next action using Ollama Llama2."""

        system_prompt = """You are a web automation assistant. Your task is to determine the next action to take to achieve the user's objective.

AVAILABLE ACTIONS:
- click(ELEMENT_DESCRIPTION) - Click on an element described by its text or accessibility label.
- type("TEXT", into="ELEMENT_DESCRIPTION") - Type text into an input field (specify element by its description).
- COMPLETE - When the objective is achieved.

RESPONSE FORMAT:
Return a JSON object with exactly these fields:
{
    "thinking": "Your reasoning about what to do next",
    "action": "The specific action to take (e.g., click('Submit button') or type('hello', into='search input') or COMPLETE)"
}

GUIDELINES:
- Choose the most logical next step toward the objective.
- Be specific with element descriptions when clicking or typing.
- If the objective appears complete, respond with action: "COMPLETE".
- Always explain your reasoning in the thinking field.
"""

        user_prompt = f"Current Objective: {user_objective}"
        if current_context:
            user_prompt += f"\n\nCurrent Context: {current_context}"

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': system_prompt,
                    },
                    {
                        'role': 'user',
                        'content': user_prompt,
                    },
                ],
                format='json' # Request JSON output
            )

            if 'message' in response and 'content' in response['message']:
                content = response['message']['content']
                # The ollama library with format='json' should already return parsed JSON,
                # but if it's a string, try parsing.
                if isinstance(content, str):
                    try:
                        parsed_response = json.loads(content)
                    except json.JSONDecodeError as e:
                        # If JSON parsing fails, try to extract thinking and action manually as a fallback
                        # This part might need adjustment based on typical Llama2 non-JSON responses
                        return self._parse_non_json_response(content)

                elif isinstance(content, dict): # Already a dict
                    parsed_response = content
                else:
                    raise Exception("Unexpected response content type from Ollama.")


                if 'thinking' in parsed_response and 'action' in parsed_response:
                    return parsed_response
                else:
                    # If keys are missing, attempt to fill them if possible or return error/default
                    return {
                        "thinking": parsed_response.get("thinking", "Could not determine thinking from response."),
                        "action": parsed_response.get("action", "COMPLETE") # Default to COMPLETE if action is unclear
                    }
            else:
                raise Exception("No message content in Ollama response.")

        except Exception as e:
            # Fallback for errors (e.g., Ollama server not running, model not available)
            error_message = f"Failed to get response from Ollama: {str(e)}"
            print(error_message) # For server-side logging
            return {
                "thinking": f"Error interacting with Ollama: {str(e)}. Please ensure Ollama is running and the model '{self.model}' is available.",
                "action": "COMPLETE" # Stop automation on error
            }

    def _parse_non_json_response(self, content_str):
        """Fallback parser for when Ollama doesn't return valid JSON."""
        thinking = "Could not reliably parse thinking from response."
        action = "COMPLETE" # Default action on parsing failure

        # Simple heuristic: look for lines starting with Thinking: or Action:
        # This is a very basic fallback and might need improvement.
        lines = content_str.strip().split('\n') # Assuming newlines might be escaped
        for line in lines:
            if line.lower().startswith("thinking:"):
                thinking = line.split(":", 1)[1].strip()
            elif line.lower().startswith("action:"):
                action = line.split(":", 1)[1].strip()

        return {
            "thinking": thinking,
            "action": action
        }

    def test_connection(self):
        """Test the connection to Ollama server and model availability."""
        try:
            self.client.list() # Simple command to check server connection
            # Check if the model is available
            models = self.client.list()['models']
            if not any(m['name'].startswith(self.model) for m in models):
                 raise Exception(f"Model '{self.model}' not found. Available models: {[m['name'] for m in models]}")
            return True
        except Exception as e:
            print(f"Ollama connection test failed: {str(e)}")
            return False

if __name__ == '__main__':
    # Example Usage (requires Ollama server running with llama2 model)
    # ollama pull llama2 (if you haven't already)

    print("Attempting to connect to Ollama...")
    try:
        client = OllamaClient()
        if client.test_connection():
            print("Successfully connected to Ollama and model is available.")

            objective = "Find the current weather in London."
            print(f"Objective: {objective}")

            decision = client.analyze_and_decide(objective)
            print("\nResponse from Ollama:")
            print(f"  Thinking: {decision.get('thinking')}")
            print(f"  Action: {decision.get('action')}")

            objective_2 = "Book a flight from New York to Paris for next week."
            context_2 = "I am on the airline's homepage."
            print(f"\nObjective: {objective_2}")
            print(f"Context: {context_2}")
            decision_2 = client.analyze_and_decide(objective_2, current_context=context_2)
            print("\nResponse from Ollama:")
            print(f"  Thinking: {decision_2.get('thinking')}")
            print(f"  Action: {decision_2.get('action')}")

        else:
            print("Failed to connect to Ollama or model not available. Please ensure Ollama is running and the 'llama2' model is pulled.")
            print("You can run 'ollama serve' in your terminal to start the server.")
            print("And 'ollama pull llama2' to download the model.")

    except Exception as e:
        print(f"An error occurred during the example usage: {str(e)}")
        print("Please ensure Ollama is running and the 'llama2' model is pulled.")
