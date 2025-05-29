import requests
import json
import base64
import os

class MistralClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.base_url = "https://api.mistral.ai/v1"
        self.model = "pixtral-large-2411"
        
        if not self.api_key:
            raise ValueError("Mistral API key is required")
    
    def analyze_and_decide(self, image_base64, user_objective, current_context=None):
        """Analyze screenshot and decide on next action"""
        
        # Construct the prompt for analysis
        system_prompt = """You are a web automation assistant powered by computer vision. Your task is to analyze screenshots of web pages and determine the next action to take to achieve the user's objective.

AVAILABLE ACTIONS:
- click(INDEX) - Click on an element by its numbered index (shown in red circles)
- type("TEXT", into="ELEMENT") - Type text into an input field (specify element by description)
- COMPLETE - When the objective is achieved

RESPONSE FORMAT:
Return a JSON object with exactly these fields:
{
    "thinking": "Your reasoning about what you see and what to do next",
    "action": "The specific action to take (e.g., click(5) or type('hello', into='search box') or COMPLETE)"
}

GUIDELINES:
- Carefully examine all numbered elements in the image
- Choose the most logical next step toward the objective
- Be specific with element indexes when clicking
- For typing, describe the target element clearly
- If the objective appears complete, respond with action: "COMPLETE"
- Always explain your reasoning in the thinking field"""

        user_prompt = f"""Current Objective: {user_objective}

Please analyze this screenshot and determine the next action to take. The image shows a webpage with numbered red circles indicating clickable elements. Choose the appropriate action to progress toward the objective."""

        if current_context:
            user_prompt += f"\n\nCurrent Context: {current_context}"

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
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
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 1000
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            if 'choices' not in result or not result['choices']:
                raise Exception("No response from API")
            
            content = result['choices'][0]['message']['content']
            
            # Try to parse as JSON
            try:
                parsed_response = json.loads(content)
                if 'thinking' in parsed_response and 'action' in parsed_response:
                    return parsed_response
            except json.JSONDecodeError:
                pass
            
            # If JSON parsing fails, try to extract thinking and action manually
            lines = content.split('\n')
            thinking = ""
            action = ""
            
            for line in lines:
                if 'thinking' in line.lower() and ':' in line:
                    thinking = line.split(':', 1)[1].strip().strip('"')
                elif 'action' in line.lower() and ':' in line:
                    action = line.split(':', 1)[1].strip().strip('"')
            
            if not thinking and not action:
                # Last resort: use the entire content as thinking
                thinking = content
                action = "click(1)"  # Default action
            
            return {
                "thinking": thinking or "Analyzing the webpage...",
                "action": action or "click(1)"
            }
            
        except Exception as e:
            raise Exception(f"Failed to analyze image: {str(e)}")
    
    def test_connection(self):
        """Test the API connection"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Simple test request
            payload = {
                "model": "mistral-small-latest",
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello, this is a test."
                    }
                ],
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception:
            return False
