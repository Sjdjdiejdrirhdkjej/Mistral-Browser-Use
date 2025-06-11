import unittest
from unittest.mock import patch, Mock, MagicMock
import os
import json
from anthropic_client import AnthropicClient
import anthropic # For exceptions

# Helper classes for mocking Anthropic's response structure
class MockContentBlock:
    def __init__(self, text):
        self.text = text

class MockAnthropicMessage:
    def __init__(self, text_content, role="assistant"):
        self.content = [MockContentBlock(text=text_content)]
        self.id = "msg_mock_id_12345"
        self.model = "claude-mock-model-v1"
        self.role = role
        self.type = "message"
        self.usage = {"input_tokens": 50, "output_tokens": 50} # Example usage data

class TestAnthropicClient(unittest.TestCase):

    # 1. API Key and Initialization Tests
    @patch('anthropic.Anthropic')
    def test_init_success_with_api_key_arg(self, MockAnthropic):
        mock_anthropic_instance = MockAnthropic.return_value
        client = AnthropicClient(api_key="fake_direct_key")
        self.assertIsNotNone(client.client)
        MockAnthropic.assert_called_once_with(api_key="fake_direct_key")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake_env_key"}, clear=True)
    @patch('anthropic.Anthropic')
    def test_init_success_with_env_var(self, MockAnthropic):
        mock_anthropic_instance = MockAnthropic.return_value
        client = AnthropicClient()
        self.assertIsNotNone(client.client)
        MockAnthropic.assert_called_once_with(api_key="fake_env_key")

    @patch.dict(os.environ, {}, clear=True) # Ensure no relevant env var
    def test_init_failure_no_api_key(self):
        with self.assertRaisesRegex(ValueError, "Anthropic API key is required"):
            AnthropicClient(api_key=None)

    @patch('anthropic.Anthropic', side_effect=Exception("Anthropic Init Failed"))
    def test_init_anthropic_client_exception(self, MockAnthropic):
        with self.assertRaisesRegex(ValueError, "Failed to initialize Anthropic client: Anthropic Init Failed"):
            AnthropicClient(api_key="fake_key")

    # 2. test_connection() Tests
    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None) # Bypass __init__
    def test_test_connection_success(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        # Mock the response for messages.create
        mock_response = MockAnthropicMessage(text_content="Hello")
        client.client.messages.create = MagicMock(return_value=mock_response)

        self.assertTrue(client.test_connection())
        client.client.messages.create.assert_called_once_with(
            model="test-model",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hello, world"}]
        )

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_auth(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.messages.create = MagicMock(side_effect=anthropic.AuthenticationError("Auth error"))
        self.assertFalse(client.test_connection())

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_connection(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.messages.create = MagicMock(side_effect=anthropic.APIConnectionError("Conn error"))
        self.assertFalse(client.test_connection())

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_rate_limit(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.messages.create = MagicMock(side_effect=anthropic.RateLimitError("Rate limit error"))
        self.assertFalse(client.test_connection())

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_test_connection_failure_generic(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.client.messages.create = MagicMock(side_effect=Exception("Generic error"))
        self.assertFalse(client.test_connection())

    # 3. generate_steps_for_todo() Tests
    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None) # Bypass __init__ for this test
    def test_generate_steps_success(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        mock_response_text = "- Step 1\n- Step 2\n- Another item"
        mock_anthropic_msg = MockAnthropicMessage(text_content=mock_response_text)
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        steps = client.generate_steps_for_todo("Generate some steps")
        self.assertEqual(steps, ["Step 1", "Step 2", "Another item"])
        client.client.messages.create.assert_called_once() # Further checks on call args can be added

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print') # Mock print to check error messages
    def test_generate_steps_api_error(self, mock_print):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        client.client.messages.create = MagicMock(side_effect=anthropic.APIError("API failed"))

        steps = client.generate_steps_for_todo("A prompt")
        self.assertEqual(steps, [])
        mock_print.assert_called_with("Error generating steps with Anthropic: API failed")

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_generate_steps_no_prefix(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_text_model = "test-model"
        mock_response_text = "Step 1 without prefix\nAnother step"
        mock_anthropic_msg = MockAnthropicMessage(text_content=mock_response_text)
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        steps = client.generate_steps_for_todo("Generate steps without prefix")
        self.assertEqual(steps, ["Step 1 without prefix", "Another step"])

    # 4. analyze_state_vision() Tests
    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_success(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"error": None, "task_completed": True, "objective_completed": "false", "summary": "All good."}
        mock_anthropic_msg = MockAnthropicMessage(text_content=json.dumps(response_data))
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertIsNone(result["error"])
        self.assertTrue(result["task_completed"])
        self.assertFalse(result["objective_completed"]) # Check boolean normalization
        self.assertEqual(result["summary"], "All good.")

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_malformed_json(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        mock_anthropic_msg = MockAnthropicMessage(text_content="Not a JSON {")
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertEqual(result["summary"], "No JSON object found in AI response.")
        self.assertIn("raw_ai_output", result)

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_state_vision_missing_keys(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"error": None, "summary": "Missing some keys."} # Missing task_completed
        mock_anthropic_msg = MockAnthropicMessage(text_content=json.dumps(response_data))
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertEqual(result["summary"], "AI response JSON missing required keys.")
        self.assertIn("raw_ai_output", result)

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_analyze_state_vision_api_error(self, mock_print):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        client.client.messages.create = MagicMock(side_effect=anthropic.APIError("Vision API error"))

        result = client.analyze_state_vision("base64img", "task", "objective")
        self.assertEqual(result["error"], "API call failed: Vision API error")
        mock_print.assert_called_with("Error in analyze_state_vision with Anthropic: Vision API error")

    # 5. analyze_and_decide() Tests
    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_success(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"thinking": "I should click.", "action": "click(1)"}
        mock_anthropic_msg = MockAnthropicMessage(text_content=json.dumps(response_data))
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "I should click.")
        self.assertEqual(result["action"], "click(1)")

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_malformed_json(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        mock_anthropic_msg = MockAnthropicMessage(text_content="This is not JSON at all.")
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "No JSON object found in AI decision response.")
        self.assertIn("raw_ai_output", result)

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    def test_analyze_and_decide_missing_keys(self):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        response_data = {"action": "click(1)"} # Missing "thinking"
        mock_anthropic_msg = MockAnthropicMessage(text_content=json.dumps(response_data))
        client.client.messages.create = MagicMock(return_value=mock_anthropic_msg)

        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "AI response JSON missing required keys (thinking/action).")
        self.assertIn("raw_ai_output", result)

    @patch.object(AnthropicClient, '__init__', lambda self, api_key=None: None)
    @patch('builtins.print')
    def test_analyze_and_decide_api_error(self, mock_print):
        client = AnthropicClient(api_key="fake_key")
        client.client = MagicMock()
        client.default_vision_model = "vision-model"
        client.client.messages.create = MagicMock(side_effect=anthropic.APIError("Decision API error"))

        result = client.analyze_and_decide("base64img", "objective")
        self.assertEqual(result["thinking"], "API call failed during decision: Decision API error")
        mock_print.assert_called_with("Error in analyze_and_decide with Anthropic: Decision API error")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) # Added exit=False for Streamlit context
```
