import requests
import json
import os

class OllamaClient:
    def __init__(self, host="http://localhost:11434"):
        self.base_url = host
        self.model = "llama2"  # Default to llama2

    def analyze_and_decide(self, image_base64, user_objective, current_context=None):
        system_prompt = """You are a web automation assistant. Your task is to analyze a description of a web page (potentially with visual elements described by the user) and determine the next action to achieve the user's objective.

AVAILABLE ACTIONS:
- click(INDEX) - Click on an element by its numbered index (as described by the user).
- type("TEXT", into="ELEMENT_DESCRIPTION") - Type text into an input field (specify element by its textual description).
- COMPLETE - When the objective is achieved.

RESPONSE FORMAT:
Return a JSON object with exactly these fields:
{
    "thinking": "Your reasoning about what you see (based on user description) and what to do next.",
    "action": "The specific action to take (e.g., click(5) or type('hello', into='search box') or COMPLETE)."
}

GUIDELINES:
- Carefully consider the user's description of the webpage elements.
- Choose the most logical next step toward the objective.
- Be specific with element indexes when clicking, based on the user's numbering.
- For typing, describe the target element clearly based on user's input.
- If the objective appears complete, respond with action: "COMPLETE".
- Always explain your reasoning in the thinking field.
- The user will provide details about the image, including numbered elements. You will not receive the image directly."""

        user_prompt_content = f"Current Objective: {user_objective}\n\n"
        user_prompt_content += "I am looking at a webpage screenshot. I will describe the relevant elements and their numbers.\n"
        if image_base64:
            user_prompt_content += "The screenshot has been processed and elements are indexed.\n"
        if current_context:
            user_prompt_content += f"Current Context/Elements Description: {current_context}\n\n"
        user_prompt_content += "Please analyze this information and determine the next action."

        try:
            headers = {
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt_content
                    }
                ],
                "stream": False,
                "format": "json" # Request JSON output
            }

            response = requests.post(
                f"{self.base_url}/api/chat",
                headers=headers,
                json=payload,
                timeout=60
            )

            response.raise_for_status()

            result = response.json()

            if result.get("message") and result["message"].get("content"):
                content = result["message"]["content"]
                try:
                    parsed_response = json.loads(content)
                    if 'thinking' in parsed_response and 'action' in parsed_response:
                        return parsed_response
                    else:
                        return {
                            "thinking": "Received a JSON response, but it's missing 'thinking' or 'action'. Content: " + content,
                            "action": "COMPLETE"
                        }
                except json.JSONDecodeError:
                    return {
                        "thinking": "Failed to parse JSON response from Ollama. Content: " + content,
                        "action": "COMPLETE"
                    }
            else:
                raise Exception(f"Unexpected response structure from Ollama: {result}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to analyze with Ollama: {str(e)}")

    def test_connection(self):
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            # Check if 'models' key is in the JSON response, which is typical for /api/tags
            data = response.json()
            return "models" in data
        except requests.exceptions.RequestException:
            return False
        except json.JSONDecodeError: # If response is not JSON or empty
            return False
        except Exception: # Catch any other unexpected errors
            return False
