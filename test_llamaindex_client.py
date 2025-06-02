import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import json
import os

# Ensure llamaindex_client can be imported.
# This assumes test_llamaindex_client.py is in the same directory as llamaindex_client.py
# or that the project root is in sys.path.
try:
    from llamaindex_client import LlamaIndexClient
except ImportError:
    # Fallback if running from a different structure, adjust as needed
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from llamaindex_client import LlamaIndexClient

from llama_index.core.llms import CompletionResponse as LlamaCompletionResponse
from llama_index.core.multi_modal_llms import MultiModalCompletionResponse as LlamaMultiModalCompletionResponse
from llama_index.core.base.llms.types import MessageRole, ChatMessage


# Mocks for LlamaIndex response objects
def create_mock_completion_response(text: str):
    return LlamaCompletionResponse(text=text)

def create_mock_chat_response(text: str):
    return ChatMessage(role=MessageRole.ASSISTANT, content=text)

def create_mock_multimodal_completion_response(text: str):
    # This might need more specific mocking if other attributes of MultiModalCompletionResponse are used
    return LlamaMultiModalCompletionResponse(text=text)


@patch('llamaindex_client.OllamaMultiModal')
@patch('llamaindex_client.Ollama')
class TestLlamaIndexClient(unittest.TestCase):

    def test_initialization_default(self, MockOllama, MockOllamaMultiModal):
        client = LlamaIndexClient()
        MockOllama.assert_called_once_with(
            model="qwen2.5vl",
            base_url="http://localhost:11434",
            request_timeout=120.0,
            temperature=0.1,
            format="json"
        )
        MockOllamaMultiModal.assert_called_once_with(
            model="qwen2.5vl",
            base_url="http://localhost:11434",
            request_timeout=120.0,
            temperature=0.1,
            format="json"
        )
        self.assertEqual(client.model_name, "qwen2.5vl")
        self.assertEqual(client.ollama_base_url, "http://localhost:11434") # Check that base_url is now hardcoded

    def test_initialization_custom_model_no_base_url_param(self, MockOllama, MockOllamaMultiModal):
        # Test with only model_name and request_timeout, base_url should be default
        client = LlamaIndexClient(model_name="custom_model", request_timeout=60.0)
        MockOllama.assert_called_once_with(
            model="custom_model",
            base_url="http://localhost:11434", # Assert default base_url
            request_timeout=60.0,
            temperature=0.1,
            format="json"
        )
        MockOllamaMultiModal.assert_called_once_with(
            model="custom_model",
            base_url="http://localhost:11434", # Assert default base_url
            request_timeout=60.0,
            temperature=0.1,
            format="json"
        )
        self.assertEqual(client.model_name, "custom_model")
        self.assertEqual(client.ollama_base_url, "http://localhost:11434")


    @patch('llamaindex_client.subprocess.run')
    def test_is_model_available_success(self, mock_subproc_run, MockOllama, MockOllamaMultiModal):
        client = LlamaIndexClient()
        mock_subproc_run.return_value = MagicMock(stdout="qwen2.5vl:latest\nothermodel:latest", returncode=0)
        self.assertTrue(client.is_model_available("qwen2.5vl"))
        mock_subproc_run.assert_called_with(['ollama', 'list'], capture_output=True, text=True, check=False)

    @patch('llamaindex_client.subprocess.run')
    def test_is_model_available_failure(self, mock_subproc_run, MockOllama, MockOllamaMultiModal):
        client = LlamaIndexClient()
        mock_subproc_run.return_value = MagicMock(stdout="othermodel:latest", returncode=0)
        self.assertFalse(client.is_model_available("qwen2.5vl"))

    @patch('llamaindex_client.subprocess.run')
    def test_is_model_available_command_error(self, mock_subproc_run, MockOllama, MockOllamaMultiModal):
        client = LlamaIndexClient()
        mock_subproc_run.return_value = MagicMock(stderr="command error", returncode=1)
        self.assertFalse(client.is_model_available("qwen2.5vl"))

    @patch('llamaindex_client.subprocess.Popen')
    def test_pull_model_success(self, mock_popen, MockOllama, MockOllamaMultiModal):
        client = LlamaIndexClient()
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("Model pulled", "") # stdout, stderr
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        success, message = client.pull_model("qwen2.5vl")
        self.assertTrue(success)
        self.assertIn("Successfully pulled model", message)
        mock_popen.assert_called_with(
            ["ollama", "pull", "qwen2.5vl"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8'
        )

    @patch('llamaindex_client.subprocess.Popen')
    def test_pull_model_failure(self, mock_popen, MockOllama, MockOllamaMultiModal):
        client = LlamaIndexClient()
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "Error pulling model") # stdout, stderr
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        success, message = client.pull_model("qwen2.5vl")
        self.assertFalse(success)
        self.assertIn("Failed to pull model", message)
        self.assertIn("Error pulling model", message)

    def test_generate_steps_success_json_list(self, MockOllama, MockOllamaMultiModal):
        mock_llm_instance = MockOllama.return_value
        # Simulate that the LLM returns a JSON string that is a list
        mock_llm_instance.chat.return_value = create_mock_chat_response(text='["Step 1", "Step 2", "Step 3"]')

        client = LlamaIndexClient()
        steps = client.generate_steps_for_todo("Some objective")

        self.assertEqual(steps, ["Step 1", "Step 2", "Step 3"])
        mock_llm_instance.chat.assert_called_once()

    def test_generate_steps_success_json_dict(self, MockOllama, MockOllamaMultiModal):
        mock_llm_instance = MockOllama.return_value
        mock_llm_instance.chat.return_value = create_mock_chat_response(text='{"steps": ["Step A", "Step B"]}')

        client = LlamaIndexClient()
        steps = client.generate_steps_for_todo("Another objective")

        self.assertEqual(steps, ["Step A", "Step B"])

    def test_generate_steps_non_json_fallback(self, MockOllama, MockOllamaMultiModal):
        mock_llm_instance = MockOllama.return_value
        mock_llm_instance.chat.return_value = create_mock_chat_response(text="- Step X\n- Step Y")

        client = LlamaIndexClient()
        steps = client.generate_steps_for_todo("Fallback objective")
        # Based on current fallback, it should split by newline and clean up
        self.assertEqual(steps, ["Step X", "Step Y"])

    def test_generate_steps_api_error(self, MockOllama, MockOllamaMultiModal):
        mock_llm_instance = MockOllama.return_value
        mock_llm_instance.chat.side_effect = Exception("LLM API Error")

        client = LlamaIndexClient()
        steps = client.generate_steps_for_todo("Error objective")

        self.assertIsInstance(steps, list)
        self.assertTrue(len(steps) == 1)
        self.assertIn("Error generating steps: LLM API Error", steps[0])

    @patch('llamaindex_client.ImageDocument')
    def test_analyze_and_decide_success(self, MockImageDocument, MockOllama, MockOllamaMultiModal):
        mock_mm_llm_instance = MockOllamaMultiModal.return_value
        mock_response_json = {"thinking": "I see a button.", "action": "click(1)"}
        mock_mm_llm_instance.chat.return_value = create_mock_chat_response(text=json.dumps(mock_response_json))

        # Mock ImageDocument instantiation
        mock_img_doc_instance = MockImageDocument.return_value

        client = LlamaIndexClient()
        result = client.analyze_and_decide("base64img_data", "user objective", "current task")

        self.assertEqual(result, mock_response_json)
        MockImageDocument.assert_called_once_with(image="base64img_data")
        # Check that chat was called with the image document
        args, kwargs = mock_mm_llm_instance.chat.call_args
        self.assertIn('messages', kwargs)
        user_message = next(m for m in kwargs['messages'] if m['role'] == 'user')
        self.assertIn('image_documents', user_message)
        self.assertEqual(user_message['image_documents'], [mock_img_doc_instance])


    @patch('llamaindex_client.ImageDocument')
    def test_analyze_and_decide_json_error(self, MockImageDocument, MockOllama, MockOllamaMultiModal):
        mock_mm_llm_instance = MockOllamaMultiModal.return_value
        mock_mm_llm_instance.chat.return_value = create_mock_chat_response(text="this is not valid json")

        client = LlamaIndexClient()
        result = client.analyze_and_decide("base64img_data", "user objective", "current task")

        self.assertIn("Error parsing decision", result['thinking'])
        self.assertEqual(result['action'], "")

    @patch('llamaindex_client.ImageDocument')
    def test_analyze_state_vision_success(self, MockImageDocument, MockOllama, MockOllamaMultiModal):
        mock_mm_llm_instance = MockOllamaMultiModal.return_value
        response_dict = {"summary": "Looks good.", "error": None, "task_completed": True, "objective_completed": False}
        mock_mm_llm_instance.chat.return_value = create_mock_chat_response(text=json.dumps(response_dict))

        mock_img_doc_instance = MockImageDocument.return_value

        client = LlamaIndexClient()
        result = client.analyze_state_vision("base64img_data", "current task", "objective")

        self.assertEqual(result, response_dict)
        MockImageDocument.assert_called_once_with(image="base64img_data")
        args, kwargs = mock_mm_llm_instance.chat.call_args
        user_message = next(m for m in kwargs['messages'] if m['role'] == 'user')
        self.assertEqual(user_message['image_documents'], [mock_img_doc_instance])


    @patch('llamaindex_client.ImageDocument')
    def test_analyze_state_vision_bool_parsing(self, MockImageDocument, MockOllama, MockOllamaMultiModal):
        mock_mm_llm_instance = MockOllamaMultiModal.return_value
        # Model might return booleans as strings
        response_str_bool = '{"summary": "Test bool parsing.", "error": "null", "task_completed": "true", "objective_completed": "False"}'
        mock_mm_llm_instance.chat.return_value = create_mock_chat_response(text=response_str_bool)

        client = LlamaIndexClient()
        result = client.analyze_state_vision("base64img_data", "current task", "objective")

        self.assertEqual(result['summary'], "Test bool parsing.")
        self.assertIsNone(result['error']) # "null" string should become None
        self.assertIsInstance(result['task_completed'], bool)
        self.assertTrue(result['task_completed'])
        self.assertIsInstance(result['objective_completed'], bool)
        self.assertFalse(result['objective_completed'])

    @patch('llamaindex_client.ImageDocument')
    def test_analyze_state_vision_actual_bool_from_json(self, MockImageDocument, MockOllama, MockOllamaMultiModal):
        mock_mm_llm_instance = MockOllamaMultiModal.return_value
        # Model returns actual booleans in JSON
        response_actual_bool = '{"summary": "Test actual bool.", "error": null, "task_completed": false, "objective_completed": true}'
        mock_mm_llm_instance.chat.return_value = create_mock_chat_response(text=response_actual_bool)

        client = LlamaIndexClient()
        result = client.analyze_state_vision("base64img_data", "current task", "objective")

        self.assertFalse(result['task_completed'])
        self.assertTrue(result['objective_completed'])


if __name__ == '__main__':
    unittest.main()
