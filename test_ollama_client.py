import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import json
import os

# Add project root to sys.path to allow importing ollama_client
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))) # Assuming test file is in the same dir as ollama_client.py or project root

from ollama_client import OllamaClient
import ollama # Import for ollama.ResponseError

# Helper to create a mock subprocess.CompletedProcess
def make_completed_process(stdout='', stderr='', returncode=0):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc

class TestOllamaClient(unittest.TestCase):

    def test_init_default_host(self):
        client = OllamaClient()
        self.assertEqual(client.client._client.host, 'http://localhost:11434')

    def test_init_custom_host(self):
        custom_host = 'http://customhost:12345'
        client = OllamaClient(host=custom_host)
        self.assertEqual(client.client._client.host, custom_host)

    @patch('ollama.Client.list')
    def test_list_models_success(self, mock_ollama_list):
        expected_models = [{'name': 'llama3.2:latest', 'size': 123}, {'name': 'llava:latest', 'size': 456}]
        mock_ollama_list.return_value = {'models': expected_models}

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(models, expected_models)
        mock_ollama_list.assert_called_once()

    @patch('ollama.Client.list')
    def test_list_models_api_error(self, mock_ollama_list):
        # Simulate a connection error or other API error
        mock_ollama_list.side_effect = ollama.ResponseError("Connection error", status_code=500)

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(models, []) # Expect empty list on error
        mock_ollama_list.assert_called_once()

    @patch.object(OllamaClient, 'list_models')
    def test_is_model_available_present(self, mock_list_models):
        mock_list_models.return_value = [{'name': 'llama3.2:latest'}, {'name': 'llava:7b'}]
        client = OllamaClient()
        self.assertTrue(client.is_model_available('llama3.2'))
        self.assertTrue(client.is_model_available('llava'))
        mock_list_models.assert_called()

    @patch.object(OllamaClient, 'list_models')
    def test_is_model_available_absent(self, mock_list_models):
        mock_list_models.return_value = [{'name': 'llama3.2:latest'}]
        client = OllamaClient()
        self.assertFalse(client.is_model_available('codellama'))
        mock_list_models.assert_called_once()

    @patch('subprocess.Popen')
    @patch.object(OllamaClient, 'is_model_available', return_value=True) # Assume model becomes available
    def test_pull_model_success(self, mock_is_available, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("Success output", "") # stdout, stderr
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        client = OllamaClient()
        success, message = client.pull_model('llama3.2')

        self.assertTrue(success)
        self.assertIn("Successfully pulled model 'llama3.2'", message)
        mock_popen.assert_called_once_with(
            ["ollama", "pull", "llama3.2"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8'
        )
        mock_is_available.assert_called_with('llama3.2')


    @patch('subprocess.Popen')
    @patch.object(OllamaClient, 'is_model_available', return_value=True) # Mock to simulate "already exists"
    def test_pull_model_already_exists(self, mock_is_available, mock_popen):
        mock_process = MagicMock()
        # Ollama sometimes puts "already exists" on stderr even with returncode 0
        mock_process.communicate.return_value = ("", "layer already exists, skipping")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        client = OllamaClient()
        success, message = client.pull_model('llama3.2')

        self.assertTrue(success)
        self.assertIn("Model 'llama3.2' already exists locally.", message)
        mock_popen.assert_called_once_with(
            ["ollama", "pull", "llama3.2"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8'
        )
        # is_model_available is not called in the "already exists" specific branch of pull_model after communicate()
        # but it might be called by the initial check in the main logic of the app, so allow calls.
        # mock_is_available.assert_not_called() # or assert_called_once_with('llama3.2') depending on desired flow if it's used for final check


    @patch('subprocess.Popen')
    def test_pull_model_failure_return_code(self, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "Error pulling model") # stdout, stderr
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        client = OllamaClient()
        success, message = client.pull_model('error_model')

        self.assertFalse(success)
        self.assertIn("Failed to pull model 'error_model'. Error: Error pulling model", message)
        mock_popen.assert_called_once()

    @patch('subprocess.Popen', side_effect=FileNotFoundError("ollama not found"))
    def test_pull_model_file_not_found(self, mock_popen):
        client = OllamaClient()
        success, message = client.pull_model('any_model')
        self.assertFalse(success)
        self.assertIn("Error: 'ollama' command not found.", message)
        mock_popen.assert_called_once()

    @patch('ollama.Client.chat')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fakeimagedata')
    def test_analyze_and_decide_success(self, mock_file_open, mock_ollama_chat):
        expected_response = {"thinking": "Test thinking", "action": "click(1)"}
        mock_ollama_chat.return_value = {
            'message': {
                'content': json.dumps(expected_response)
            }
        }
        client = OllamaClient()
        result = client.analyze_and_decide('dummy_image.png', 'test task', 'test objective', model_name='llava')

        self.assertEqual(result, expected_response)
        mock_ollama_chat.assert_called_once()
        # Check that image_bytes are passed to ollama.chat
        args, kwargs = mock_ollama_chat.call_args
        self.assertIn('messages', kwargs)
        user_message = next(m for m in kwargs['messages'] if m['role'] == 'user')
        self.assertEqual(user_message['images'], [b'fakeimagedata'])


    @patch('ollama.Client.chat')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fakeimagedata')
    def test_analyze_and_decide_json_parsing_error(self, mock_file_open, mock_ollama_chat):
        mock_ollama_chat.return_value = {
            'message': {
                'content': "This is not JSON"
            }
        }
        client = OllamaClient()
        result = client.analyze_and_decide('dummy_image.png', 'test task', 'test objective')

        self.assertIn("Failed to parse LLaVA response as JSON", result['thinking'])
        self.assertEqual(result['action'], "")

    @patch('ollama.Client.chat', side_effect=ollama.ResponseError("Model not found", status_code=404))
    @patch('builtins.open', new_callable=mock_open, read_data=b'fakeimagedata')
    def test_analyze_and_decide_api_error_404(self, mock_file_open, mock_ollama_chat):
        client = OllamaClient()
        result = client.analyze_and_decide('dummy_image.png', 'test task', 'test objective', model_name='non_existent_model')
        self.assertIn("Error: Model 'non_existent_model' not found", result['thinking'])
        self.assertEqual(result['action'], "")


    @patch('ollama.Client.generate')
    def test_generate_steps_for_todo_success(self, mock_ollama_generate):
        expected_steps = ["Step 1", "Step 2"]
        mock_ollama_generate.return_value = {'response': json.dumps(expected_steps)}

        client = OllamaClient()
        steps = client.generate_steps_for_todo("Plan a picnic")

        self.assertEqual(steps, expected_steps)
        mock_ollama_generate.assert_called_once()
        args, kwargs = mock_ollama_generate.call_args
        self.assertEqual(kwargs['format'], 'json')


    @patch('ollama.Client.generate')
    def test_generate_steps_for_todo_json_parsing_error(self, mock_ollama_generate):
        mock_ollama_generate.return_value = {'response': "Not a JSON list"}
        client = OllamaClient()
        steps = client.generate_steps_for_todo("Plan something complex")
        self.assertIsInstance(steps, list)
        self.assertTrue(len(steps) >= 1)
        self.assertIn("Failed to parse steps as JSON. Raw output: Not a JSON list", steps[0])

    @patch('ollama.Client.generate', side_effect=ollama.ResponseError("API Error", status_code=500))
    def test_generate_steps_for_todo_api_error(self, mock_ollama_generate):
        client = OllamaClient()
        steps = client.generate_steps_for_todo("Plan something")
        self.assertIsInstance(steps, list)
        self.assertTrue(len(steps) == 1)
        self.assertIn("Error: Ollama API error", steps[0])


    @patch('ollama.Client.chat')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fakeimagedata')
    def test_analyze_state_vision_success(self, mock_file_open, mock_ollama_chat):
        api_response = {
            "summary": "Task is done.",
            "error": None,
            "task_completed": True,
            "objective_completed": False
        }
        mock_ollama_chat.return_value = {
            'message': {
                'content': json.dumps(api_response)
            }
        }
        client = OllamaClient()
        result = client.analyze_state_vision('dummy.png', 'prev', 'curr', 'next', 'obj')

        self.assertEqual(result['summary'], "Task is done.")
        self.assertIsNone(result['error'])
        self.assertTrue(result['task_completed'])
        self.assertFalse(result['objective_completed'])
        mock_ollama_chat.assert_called_once()
        args, kwargs = mock_ollama_chat.call_args
        self.assertEqual(kwargs['format'], 'json')
        user_message = next(m for m in kwargs['messages'] if m['role'] == 'user')
        self.assertEqual(user_message['images'], [b'fakeimagedata'])


    @patch('ollama.Client.chat')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fakeimagedata')
    def test_analyze_state_vision_json_parsing_error(self, mock_file_open, mock_ollama_chat):
        mock_ollama_chat.return_value = {
            'message': {
                'content': "Not JSON at all"
            }
        }
        client = OllamaClient()
        result = client.analyze_state_vision('dummy.png', 'prev', 'curr', 'next', 'obj')
        self.assertIn("Failed to parse LLaVA response as JSON", result['summary'])
        self.assertEqual(result['error'], "JSON parsing failed")
        self.assertFalse(result['task_completed'])
        self.assertFalse(result['objective_completed'])

    @patch('ollama.Client.chat')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fakeimagedata')
    def test_analyze_state_vision_boolean_string_conversion(self, mock_file_open, mock_ollama_chat):
        # Test if "true" (string) from API is converted to True (bool)
        api_response_str_bool = {
            "summary": "Task is done.",
            "error": "None", # Test "None" string for error
            "task_completed": "true", # String true
            "objective_completed": "false" # String false
        }
        mock_ollama_chat.return_value = {
            'message': {
                'content': json.dumps(api_response_str_bool)
            }
        }
        client = OllamaClient()
        result = client.analyze_state_vision('dummy.png', 'prev', 'curr', 'next', 'obj')

        self.assertTrue(result['task_completed'])
        self.assertFalse(result['objective_completed'])
        self.assertIsNone(result['error']) # "None" string should become None


if __name__ == '__main__':
    unittest.main()
