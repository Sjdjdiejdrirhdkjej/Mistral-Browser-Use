import unittest
from unittest.mock import patch, Mock, MagicMock
import os
import json
from openai_client import OpenAIClient
import openai # For exceptions

# Helper classes for mocking OpenAI's response structure
class MockOpenAIMessage:
    def __init__(self, content_text, role="assistant"):
        self.content = content_text
        self.role = role

class MockOpenAIChoice:
    def __init__(self, content_text):
        self.message = MockOpenAIMessage(content_text)
        # Add other attributes if needed, e.g., finish_reason
        self.finish_reason = "stop"

class MockOpenAICompletionResponse:
    def __init__(self, content_text):
        self.choices = [MockOpenAIChoice(content_text)]
        self.id = "chatcmpl-mock-id-12345"
        self.model = "gpt-mock-model-v1"
        self.usage = {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}
        # Add other top-level attributes if your client uses them, e.g., created, system_fingerprint


class TestOpenAIClient(unittest.TestCase):

    # 1. API Key and Initialization Tests
    @patch('openai.OpenAI')
    def test_init_success_with_api_key_arg(self, MockOpenAI):
        mock_openai_instance = MockOpenAI.return_value
        client = OpenAIClient(api_key="fake_direct_key")
        self.assertIsNotNone(client.client)
        MockOpenAI.assert_called_once_with(api_key="fake_direct_key")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_env_key"}, clear=True)
    @patch('openai.OpenAI')
    def test_init_success_with_env_var(self, MockOpenAI):
        mock_openai_instance = MockOpenAI.return_value
        client = OpenAIClient()
        self.assertIsNotNone(client.client)
        MockOpenAI.assert_called_once_with(api_key="fake_env_key")

    @patch.dict(os.environ, {}, clear=True)
    def test_init_failure_no_api_key(self):
        with self.assertRaisesRegex(ValueError, "OpenAI API key is required"):
            OpenAIClient(api_key=None)

    @patch('openai.OpenAI', side_effect=Exception("OpenAI Init Failed"))
    def test_init_openai_client_exception(self, MockOpenAI):
        with self.assertRaisesRegex(ValueError, "Failed to initialize OpenAI client: OpenAI Init Failed"):
            OpenAIClient(api_key="fake_key")

    # 2. test_connection() Tests
    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_success(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        mock_response = MockOpenAICompletionResponse("Hello")
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        self.assertTrue(client.test_connection())
        client.client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[{"role": "user", "content": "Hello, world"}],
            max_tokens=10
        )

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_auth(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.chat.completions.create = MagicMock(side_effect=openai.AuthenticationError("Auth error", response=Mock(), body=None))
        self.assertFalse(client.test_connection())

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_connection(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.chat.completions.create = MagicMock(side_effect=openai.APIConnectionError(request=Mock()))
        self.assertFalse(client.test_connection())

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_rate_limit(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.chat.completions.create = MagicMock(side_effect=openai.RateLimitError("Rate limit error", response=Mock(), body=None))
        self.assertFalse(client.test_connection())

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_generic(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.chat.completions.create = MagicMock(side_effect=Exception("Generic error"))
        self.assertFalse(client.test_connection())

    # 3. generate_steps_for_todo() Tests
    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_generate_steps_success(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        mock_response = MockOpenAICompletionResponse("- Step 1\n- Step 2\n- Another item")
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        steps = client.generate_steps_for_todo("Generate some steps")
        self.assertEqual(steps, ["Step 1", "Step 2", "Another item"])
        client.client.chat.completions.create.assert_called_once()

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_generate_steps_api_error(self, mock_print):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        client.client.chat.completions.create = MagicMock(side_effect=openai.APIError("API failed", request=Mock(), body=None))

        steps = client.generate_steps_for_todo("A prompt")
        self.assertEqual(steps, [])
        mock_print.assert_called_with("Error generating steps with OpenAI: API failed")

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_generate_steps_no_prefix(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        mock_response = MockOpenAICompletionResponse("Step 1 without prefix\nAnother step")
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        steps = client.generate_steps_for_todo("Generate steps without prefix")
        self.assertEqual(steps, ["Step 1 without prefix", "Another step"])

    # 4. analyze_state_vision() Tests
    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_success_json_mode(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"error": None, "task_completed": True, "objective_completed": "false", "summary": "All good."}
        mock_response = MockOpenAICompletionResponse(json.dumps(response_data))
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertIsNone(result["error"])
        self.assertTrue(result["task_completed"])
        self.assertFalse(result["objective_completed"])
        self.assertEqual(result["summary"], "All good.")
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('response_format'), {"type": "json_object"})


    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_success_text_fallback(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"error": "An error", "task_completed": "false", "objective_completed": "true", "summary": "Fallback."}
        # Simulate JSON mode failure leading to fallback
        client.client.chat.completions.create = MagicMock(
            side_effect=[
                openai.APIError("JSON mode not supported", request=Mock(), body=None), # First call fails (simulating JSON mode failure)
                MockOpenAICompletionResponse(f"Some text around ```json\n{json.dumps(response_data)}\n```") # Second call (fallback)
            ]
        )
        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertEqual(result["error"], "An error")
        self.assertFalse(result["task_completed"])
        self.assertTrue(result["objective_completed"])
        self.assertEqual(result["summary"], "Fallback.")
        self.assertEqual(client.client.chat.completions.create.call_count, 2) # Called once for JSON mode, once for fallback

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_malformed_json(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse("Not a JSON {"))
        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertEqual(result["summary"], "Failed to decode JSON from AI response (even with fallback).") # Updated expected message
        self.assertIn("raw_ai_output", result)


    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_missing_keys(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"error": None, "summary": "Missing some keys."}
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))
        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertEqual(result["summary"], "AI response JSON missing required keys.")
        self.assertIn("raw_ai_output", result)

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_analyze_state_vision_api_error(self, mock_print):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        client.client.chat.completions.create = MagicMock(side_effect=openai.APIError("Vision API error", request=Mock(), body=None))
        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertEqual(result["error"], "API call failed: Vision API error")
        mock_print.assert_called_with("Error in analyze_state_vision with OpenAI: Vision API error")

    # 5. analyze_and_decide() Tests
    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_success_json_mode(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"thinking": "I should click.", "action": "click(1)"}
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))
        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "I should click.")
        self.assertEqual(result["action"], "click(1)")
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('response_format'), {"type": "json_object"})

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_success_text_fallback(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"thinking": "Fallback thinking.", "action": "type('text', into='field')"}
        client.client.chat.completions.create = MagicMock(
            side_effect=[
                openai.APIError("JSON mode not supported", request=Mock(), body=None),
                MockOpenAICompletionResponse(f"Text ```json\n{json.dumps(response_data)}\n``` end")
            ]
        )
        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "Fallback thinking.")
        self.assertEqual(result["action"], "type('text', into='field')")
        self.assertEqual(client.client.chat.completions.create.call_count, 2)

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_malformed_json(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse("This is not JSON"))
        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "Failed to decode JSON from AI response for decision (even with fallback).") # Updated
        self.assertIn("raw_ai_output", result)

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_missing_keys(self):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"action": "click(1)"} # Missing "thinking"
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))
        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "AI response JSON missing required keys (thinking/action).")
        self.assertIn("raw_ai_output", result)

    @patch.object(OpenAIClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_analyze_and_decide_api_error(self, mock_print):
        client = OpenAIClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        client.client.chat.completions.create = MagicMock(side_effect=openai.APIError("Decision API error", request=Mock(), body=None))
        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "API call failed during decision: Decision API error")
        mock_print.assert_called_with("Error in analyze_and_decide with OpenAI: Decision API error")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
```
