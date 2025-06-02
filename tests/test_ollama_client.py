import unittest
from unittest.mock import patch, Mock
import sys
import os

# Adjust path to import OllamaClient from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ollama_client import OllamaClient
import requests # Required for requests.exceptions

class TestOllamaClient(unittest.TestCase):

    def setUp(self):
        self.client = OllamaClient(base_url="http://mock-ollama:11434/api")

    @patch('ollama_client.requests.get')
    def test_list_models_success(self, mock_get):
        # Configure the mock response for requests.get
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama2:latest", "modified_at": "2023-10-26T14:00:00Z", "size": 7000000000},
                {"name": "codellama:latest", "modified_at": "2023-10-25T10:00:00Z", "size": 7000000000}
            ]
        }
        mock_get.return_value = mock_response

        # Call the method under test
        models = self.client.list_models()

        # Assertions
        self.assertEqual(len(models), 2)
        self.assertIn("llama2:latest", models)
        self.assertIn("codellama:latest", models)
        mock_get.assert_called_once_with(f"{self.client.base_url}/tags", timeout=10)

    @patch('ollama_client.requests.post')
    def test_generate_completion_success(self, mock_post):
        # Configure the mock response for requests.post
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama2",
            "created_at": "2023-10-26T14:05:00Z",
            "response": "This is a test completion.",
            "done": True,
            "context": [1, 2, 3] # Example context
        }
        mock_post.return_value = mock_response

        prompt_text = "Tell me a joke."
        model_to_use = "llama2" # Default, but explicitly passed for clarity in test

        # Call the method under test
        completion = self.client.generate_completion(prompt=prompt_text, model_name=model_to_use)

        # Assertions
        self.assertEqual(completion, "This is a test completion.")

        expected_payload = {
            "model": model_to_use,
            "prompt": prompt_text,
            "stream": False
        }
        mock_post.assert_called_once_with(
            f"{self.client.base_url}/generate",
            headers={"Content-Type": "application/json"},
            json=expected_payload,
            timeout=60
        )

    @patch('ollama_client.requests.post')
    def test_generate_completion_with_image_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llava:latest",
            "response": "Image processed.",
            "done": True
        }
        mock_post.return_value = mock_response

        prompt_text = "What is in this image?"
        model_to_use = "llava:latest"
        image_b64 = "fakebase64string"

        completion = self.client.generate_completion(prompt=prompt_text, model_name=model_to_use, image_base64=image_b64)
        self.assertEqual(completion, "Image processed.")

        expected_payload = {
            "model": model_to_use,
            "prompt": prompt_text,
            "stream": False,
            "images": [image_b64]
        }
        mock_post.assert_called_once_with(
            f"{self.client.base_url}/generate",
            headers={"Content-Type": "application/json"},
            json=expected_payload,
            timeout=60
        )

    @patch('ollama_client.requests.get')
    def test_list_models_api_error(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_response.text = "Internal Server Error" # Mocking the text attribute for the error message
        mock_get.return_value = mock_response

        models = self.client.list_models()
        self.assertEqual(models, []) # Expect an empty list on error
        mock_get.assert_called_once_with(f"{self.client.base_url}/tags", timeout=10)

    @patch('ollama_client.requests.post')
    def test_generate_completion_api_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_response.text = "Internal Server Error" # Mocking the text attribute
        mock_post.return_value = mock_response

        # Assign the mock response to the 'response' attribute of the mock_post object itself,
        # which is what would be accessed as e.response in the client code.
        # However, the actual exception object (e) has the response attribute, so we need to ensure
        # the side_effect raises an exception that has a 'response' attribute.
        exception_with_response = requests.exceptions.HTTPError("Server Error")
        exception_with_response.response = mock_response # Attach the mock_response here
        mock_post.side_effect = exception_with_response


        completion = self.client.generate_completion(prompt="test", model_name="llama2")
        self.assertIsNone(completion) # Expect None on error
        mock_post.assert_called_once()

if __name__ == '__main__':
    unittest.main()
