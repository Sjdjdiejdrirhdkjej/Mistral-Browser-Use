import unittest
from unittest.mock import patch, Mock, MagicMock
import os
import json
from openrouter_client import OpenRouterClient
import openai # For exceptions and mocking the base client

# Helper classes for mocking OpenAI's response structure (reused)
class MockOpenAIMessage:
    def __init__(self, content_text, role="assistant"):
        self.content = content_text
        self.role = role

class MockOpenAIChoice:
    def __init__(self, content_text):
        self.message = MockOpenAIMessage(content_text)
        self.finish_reason = "stop"

class MockOpenAICompletionResponse:
    def __init__(self, content_text):
        self.choices = [MockOpenAIChoice(content_text)]
        self.id = "chatcmpl-or-mock-id-12345"
        self.model = "or-mock-model-v1" # Indicate it's an OpenRouter model
        self.usage = {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}


class TestOpenRouterClient(unittest.TestCase):

    # 1. API Key and Initialization Tests
    @patch('openai.OpenAI')
    def test_init_success_with_api_key_arg(self, MockOpenAIConstructor):
        with patch.dict(os.environ, {}, clear=True): # Ensure no env vars interfere
            client = OpenRouterClient(api_key="fake_direct_or_key")
        self.assertIsNotNone(client.client)
        MockOpenAIConstructor.assert_called_once() # Args checked in specific test below

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake_env_or_key"}, clear=True)
    @patch('openai.OpenAI')
    def test_init_success_with_env_var(self, MockOpenAIConstructor):
        client = OpenRouterClient()
        self.assertIsNotNone(client.client)
        MockOpenAIConstructor.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_init_failure_no_api_key(self):
        with self.assertRaisesRegex(ValueError, "OpenRouter API key is required"):
            OpenRouterClient(api_key=None)

    @patch('openai.OpenAI', side_effect=Exception("OpenAI Init Failed for OR"))
    def test_init_openai_client_exception(self, MockOpenAIConstructor):
        with self.assertRaisesRegex(ValueError, "Failed to initialize OpenRouter client: OpenAI Init Failed for OR"):
            OpenRouterClient(api_key="fake_or_key")

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_or_key"}, clear=True)
    @patch('openai.OpenAI')
    def test_init_correct_base_url_and_headers(self, MockOpenAIConstructor):
        # Test with specific referrer and title
        with patch.dict(os.environ, {
            "OPENROUTER_REFERRER_URL": "http://my-test-app.com",
            "OPENROUTER_X_TITLE": "My Test App"
        }, clear=True): # Clear other env vars that might affect this test
             # Need to re-patch API key as clear=True wipes it
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_or_key"}):
                client = OpenRouterClient(api_key="test_or_key")

        MockOpenAIConstructor.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="test_or_key",
            default_headers={
                "HTTP-Referer": "http://my-test-app.com",
                "X-Title": "My Test App",
            }
        )

        # Test with default referrer and title (when env vars are not set)
        MockOpenAIConstructor.reset_mock()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_or_key_default"}, clear=True): # Clear other env vars
             with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_or_key_default"}): # Set only API key
                client = OpenRouterClient(api_key="test_or_key_default")

        MockOpenAIConstructor.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="test_or_key_default",
            default_headers={ # Expecting defaults from client implementation
                "HTTP-Referer": "http://localhost:8501",
                "X-Title": "Web Automation Assistant",
            }
        )


    # 2. test_connection() Tests (Bypassing __init__ for direct client mocking)
    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_success(self):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        client.default_text_model = "or-test-model" # Default model for test
        mock_response = MockOpenAICompletionResponse("Hello from OR")
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        self.assertTrue(client.test_connection())
        client.client.chat.completions.create.assert_called_once_with(
            model="or-test-model",
            messages=[{"role": "user", "content": "Hello, world from OpenRouter test"}],
            max_tokens=10
        )

    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_auth(self):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        client.client.chat.completions.create = MagicMock(side_effect=openai.AuthenticationError("OR Auth error", response=Mock(), body=None))
        self.assertFalse(client.test_connection())

    # ... (other connection failure tests: APIConnectionError, RateLimitError, Generic Exception - similar to OpenAI's)

    # 3. generate_steps_for_todo() Tests
    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    def test_generate_steps_success(self):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        # client.default_text_model not needed here as model_name is passed
        mock_response = MockOpenAICompletionResponse("- OR Step 1\n- OR Step 2")
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        steps = client.generate_steps_for_todo("OR prompt", model_name="openrouter/test-model")
        self.assertEqual(steps, ["OR Step 1", "OR Step 2"])
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('model'), "openrouter/test-model")

    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_generate_steps_api_error(self, mock_print):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        client.client.chat.completions.create = MagicMock(side_effect=openai.APIError("OR API failed", request=Mock(), body=None))

        steps = client.generate_steps_for_todo("OR prompt error", model_name="openrouter/error-model")
        self.assertEqual(steps, [])
        mock_print.assert_called_with("Error generating steps with OpenRouter (model: openrouter/error-model): OR API failed")

    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_generate_steps_no_model_name_uses_default(self, mock_print):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        client.default_text_model = "or-default-text-model" # Ensure default is set for test
        mock_response = MockOpenAICompletionResponse("- Default OR Step")
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        steps = client.generate_steps_for_todo("OR prompt no model", model_name=None) # Pass None for model_name
        self.assertEqual(steps, ["Default OR Step"])
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('model'), "or-default-text-model")
        mock_print.assert_called_with("Warning: No model_name provided for OpenRouter step generation, using default: or-default-text-model")


    # 4. analyze_state_vision() Tests (Simplified for brevity, focusing on model_name and fallback)
    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_success_json_mode(self):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        response_data = {"error": None, "task_completed": True, "objective_completed": "false", "summary": "OR vision good."}
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))

        result = client.analyze_state_vision("base64img", "task", "objective", model_name="or/vision-model-json")
        self.assertTrue(result["task_completed"])
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('model'), "or/vision-model-json")
        self.assertEqual(kwargs.get('response_format'), {"type": "json_object"})

    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_analyze_state_vision_success_text_fallback(self, mock_print):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        response_data = {"error": None, "task_completed": "true", "objective_completed": False, "summary": "OR vision fallback."}
        # Simulate JSON mode failure, then successful text completion
        client.client.chat.completions.create.side_effect = [
            openai.APIError("JSON mode not supported by OR model", request=Mock(), body=None), # First call fails
            MockOpenAICompletionResponse(f"```json\n{json.dumps(response_data)}\n```") # Second call (fallback)
        ]
        result = client.analyze_state_vision("base64img", "task", "objective", model_name="or/vision-model-text")
        self.assertTrue(result["task_completed"])
        self.assertEqual(client.client.chat.completions.create.call_count, 2)
        mock_print.assert_any_call("Info: JSON mode might have failed for or/vision-model-text on OpenRouter (JSON mode not supported by OR model). Trying text completion parsing.")


    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print') # To check warning
    def test_analyze_state_vision_no_model_name_uses_default(self, mock_print):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        client.default_vision_model = "or-default-vision"
        response_data = {"error": None, "task_completed": True, "objective_completed": True, "summary": "OR default vision."}
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))

        result = client.analyze_state_vision("base64img", "task", "objective", model_name=None) # Pass None
        self.assertTrue(result["objective_completed"])
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('model'), "or-default-vision")
        mock_print.assert_called_with("Warning: No model_name provided for OpenRouter vision analysis, using default: or-default-vision")


    # 5. analyze_and_decide() Tests (Simplified, focusing on model_name and fallback)
    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_success_json_mode(self):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        response_data = {"thinking": "OR think JSON.", "action": "click(1)"}
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))

        result = client.analyze_and_decide("base64img", "objective", model_name="or/decide-model-json")
        self.assertEqual(result["action"], "click(1)")
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('model'), "or/decide-model-json")
        self.assertEqual(kwargs.get('response_format'), {"type": "json_object"})

    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_analyze_and_decide_success_text_fallback(self, mock_print):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        response_data = {"thinking": "OR think text fallback.", "action": "type('yes', into='box')"}
        client.client.chat.completions.create.side_effect = [
            openai.APIError("OR JSON mode fail for decide", request=Mock(), body=None),
            MockOpenAICompletionResponse(f"Some preamble... {json.dumps(response_data)} ...some postamble")
        ]
        result = client.analyze_and_decide("base64img", "objective", model_name="or/decide-model-text")
        self.assertEqual(result["action"], "type('yes', into='box')")
        self.assertEqual(client.client.chat.completions.create.call_count, 2)
        mock_print.assert_any_call("Info: JSON mode might have failed for or/decide-model-text on OpenRouter (OR JSON mode fail for decide). Trying text completion parsing for decision.")

    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print') # To check warning
    def test_analyze_and_decide_no_model_name_uses_default(self, mock_print):
        client = OpenRouterClient(api_key="fake_or_key")
        client.client = MagicMock()
        client.default_vision_model = "or-default-decide-vision"
        response_data = {"thinking": "OR default decide.", "action": "COMPLETE"}
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))

        result = client.analyze_and_decide("base64img", "objective", model_name=None) # Pass None
        self.assertEqual(result["action"], "COMPLETE")
        args, kwargs = client.client.chat.completions.create.call_args
        self.assertEqual(kwargs.get('model'), "or-default-decide-vision")
        mock_print.assert_called_with("Warning: No model_name provided for OpenRouter decision, using default: or-default-decide-vision")


    # Add other failure cases for vision/decision (malformed JSON, missing keys, API error)
    # These would be similar to OpenAIClient tests but ensuring model_name is handled.
    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_malformed_json(self):
        client = OpenRouterClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse("Not a JSON { actually"))
        result = client.analyze_state_vision("base64img", "task", "objective", model_name="or/vision-model")
        self.assertEqual(result["summary"], "Failed to decode JSON from OpenRouter response: Expecting value: line 1 column 1 (char 0)") # Error from json.loads
        self.assertIn("raw_ai_output", result)

    @patch.object(OpenRouterClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_missing_keys(self):
        client = OpenRouterClient(api_key="fake_key")
        client.client = MagicMock()
        response_data = {"action_only": "click(1)"} # Missing "thinking" and "action" has wrong key
        client.client.chat.completions.create = MagicMock(return_value=MockOpenAICompletionResponse(json.dumps(response_data)))
        result = client.analyze_and_decide("base64img", "objective", model_name="or/decide-model")
        self.assertEqual(result["thinking"], "AI response JSON (OpenRouter) missing required keys (thinking/action).")
        self.assertIn("raw_ai_output", result)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
```
