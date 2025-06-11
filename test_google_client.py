import unittest
from unittest.mock import patch, Mock, MagicMock
import os
import json
from google_client import GoogleClient
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from PIL import Image
import io
import base64 # For actual decode in one test

# Helper to create a mock GenerateContentResponse for Google
class MockGoogleGenerateContentResponse:
    def __init__(self, text_content):
        self.text = text_content
        # If client uses response.parts or response.candidates:
        # self.parts = [MockPart(text_content)]
        # self.candidates = [MockCandidate(self.parts)]
# class MockPart: def __init__(self, text): self.text = text
# class MockCandidate: def __init__(self, parts): self.content = MockContent(parts)
# class MockContent: def __init__(self, parts): self.parts = parts


class TestGoogleClient(unittest.TestCase):

    # 1. API Key and Initialization Tests
    @patch('google.generativeai.configure')
    def test_init_success_with_api_key_arg(self, mock_genai_configure):
        client = GoogleClient(api_key="fake_direct_g_key")
        mock_genai_configure.assert_called_once_with(api_key="fake_direct_g_key")

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "fake_env_g_key"}, clear=True)
    @patch('google.generativeai.configure')
    def test_init_success_with_env_var(self, mock_genai_configure):
        client = GoogleClient()
        mock_genai_configure.assert_called_once_with(api_key="fake_env_g_key")

    @patch.dict(os.environ, {}, clear=True)
    def test_init_failure_no_api_key(self):
        with self.assertRaisesRegex(ValueError, "Google API key is required"):
            GoogleClient(api_key=None)

    @patch('google.generativeai.configure', side_effect=Exception("Google Configure Failed"))
    def test_init_google_configure_exception(self, mock_genai_configure):
        with self.assertRaisesRegex(ValueError, "Failed to configure Google AI client: Google Configure Failed"):
            GoogleClient(api_key="fake_g_key")

    # 2. test_connection() Tests
    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None) # Bypass actual __init__
    @patch('google.generativeai.GenerativeModel')
    def test_test_connection_success(self, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key") # api_key is set even if __init__ is bypassed
        client.api_key = "fake_g_key" # Ensure api_key is available for configure mock if called
        client.default_text_model = "test-model"

        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse("Hello"))

        with patch('google.generativeai.configure'): # Mock configure if test_connection re-configures
             self.assertTrue(client.test_connection())

        MockGenerativeModel.assert_called_with("test-model")
        mock_model_instance.generate_content.assert_called_once_with("Hello, world from Google AI test")


    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    def test_test_connection_failure_unauthenticated(self, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key")
        client.api_key = "fake_g_key"
        client.default_text_model = "test-model"
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content = MagicMock(side_effect=google_exceptions.Unauthenticated("Auth error"))
        with patch('google.generativeai.configure'):
            self.assertFalse(client.test_connection())

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    def test_test_connection_failure_resource_exhausted(self, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key")
        client.api_key = "fake_g_key"
        client.default_text_model = "test-model"
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content = MagicMock(side_effect=google_exceptions.ResourceExhausted("Rate limit"))
        with patch('google.generativeai.configure'):
            self.assertFalse(client.test_connection())

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    def test_test_connection_failure_generic(self, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key")
        client.api_key = "fake_g_key"
        client.default_text_model = "test-model"
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content = MagicMock(side_effect=Exception("Generic error"))
        with patch('google.generativeai.configure'):
            self.assertFalse(client.test_connection())

    # 3. generate_steps_for_todo() Tests
    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    def test_generate_steps_success(self, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key")
        client.default_text_model = "text-model"
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse("- Step 1\n- Step 2"))

        with patch('google.generativeai.configure'):
            steps = client.generate_steps_for_todo("Prompt")
        self.assertEqual(steps, ["Step 1", "Step 2"])
        MockGenerativeModel.assert_called_with("text-model")
        mock_model_instance.generate_content.assert_called_once()

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('builtins.print')
    def test_generate_steps_api_error(self, mock_print, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key")
        client.default_text_model = "text-model"
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content = MagicMock(side_effect=google_exceptions.GoogleAPIError("API failed"))

        with patch('google.generativeai.configure'):
            steps = client.generate_steps_for_todo("Prompt")
        self.assertEqual(steps, [])
        mock_print.assert_called_with("Error generating steps with Google (model: text-model): API failed")

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    def test_generate_steps_no_prefix(self, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key")
        client.default_text_model = "text-model"
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse("Step 1 no prefix\nAnother G step"))
        with patch('google.generativeai.configure'):
            steps = client.generate_steps_for_todo("Prompt no prefix")
        self.assertEqual(steps, ["Step 1 no prefix", "Another G step"])

    # 4. analyze_state_vision() Tests
    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open', return_value=MagicMock(spec=Image.Image)) # Mock Image.open
    @patch('base64.b64decode', return_value=b"fake_bytes")
    def test_analyze_state_vision_success(self, mock_b64decode, mock_image_open, MockGenerativeModel):
        client = GoogleClient(api_key="fake_g_key")
        client.default_vision_model = "vision-model"
        mock_model_instance = MockGenerativeModel.return_value
        response_data = {"error": None, "task_completed": "true", "objective_completed": False, "summary": "Vision good."}
        mock_model_instance.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse(json.dumps(response_data)))

        with patch('google.generativeai.configure'):
            result = client.analyze_state_vision("base64str", "task", "objective")

        self.assertTrue(result["task_completed"])
        self.assertFalse(result["objective_completed"])
        self.assertEqual(result["summary"], "Vision good.")
        mock_b64decode.assert_called_once_with("base64str")
        mock_image_open.assert_called_once() # With BytesIO(b"fake_bytes")
        args, _ = mock_model_instance.generate_content.call_args
        self.assertIsInstance(args[0][1], MagicMock) # Check image part

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    def test_analyze_state_vision_malformed_json(self, mock_b64, mock_img_open, MockGM):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model"
        MockGM.return_value.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse("Not JSON"))
        with patch('google.generativeai.configure'):
            result = client.analyze_state_vision("b64", "t", "o")
        self.assertEqual(result["summary"], "No valid JSON object found in Google AI response.")

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    def test_analyze_state_vision_missing_keys(self, mock_b64, mock_img_open, MockGM):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model"
        MockGM.return_value.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse(json.dumps({"summary": "Only summary"})))
        with patch('google.generativeai.configure'):
            result = client.analyze_state_vision("b64", "t", "o")
        self.assertEqual(result["summary"], "AI response JSON (Google) missing required keys.")

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    @patch('builtins.print')
    def test_analyze_state_vision_api_error(self, mock_print, mock_b64, mock_img_open, MockGM):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model"
        MockGM.return_value.generate_content = MagicMock(side_effect=google_exceptions.GoogleAPIError("G API Vision Error"))
        with patch('google.generativeai.configure'):
            result = client.analyze_state_vision("b64", "t", "o")
        self.assertEqual(result["error"], "API call failed: G API Vision Error")
        mock_print.assert_called_with("Error in analyze_state_vision with Google (model: v_model): G API Vision Error")

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('base64.b64decode', side_effect=Exception("Decode Error"))
    @patch('builtins.print')
    def test_analyze_state_vision_image_decode_error(self, mock_print, mock_b64decode):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model"
        # No need to mock GenerativeModel here as it won't be reached
        with patch('google.generativeai.configure'):
            result = client.analyze_state_vision("badb64", "t", "o")
        self.assertEqual(result["error"], "API call failed: Decode Error")
        mock_print.assert_called_with("Error in analyze_state_vision with Google (model: v_model): Decode Error")


    # 5. analyze_and_decide() Tests (Structure similar to analyze_state_vision)
    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open', return_value=MagicMock(spec=Image.Image))
    @patch('base64.b64decode', return_value=b"fake_bytes")
    def test_analyze_and_decide_success(self, mock_b64, mock_img_open, MockGM):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model_decide"
        mock_model_instance = MockGM.return_value
        response_data = {"thinking": "I should click G.", "action": "click(G1)"}
        mock_model_instance.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse(json.dumps(response_data)))
        with patch('google.generativeai.configure'):
            result = client.analyze_and_decide("b64", "obj")
        self.assertEqual(result["thinking"], "I should click G.")
        self.assertEqual(result["action"], "click(G1)")

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    def test_analyze_and_decide_malformed_json(self, mock_b64, mock_img_open, MockGM):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model"
        MockGM.return_value.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse("Malformed G JSON"))
        with patch('google.generativeai.configure'):
            result = client.analyze_and_decide("b64", "obj")
        self.assertEqual(result["thinking"], "No valid JSON object found in Google AI decision response.")

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    def test_analyze_and_decide_missing_keys(self, mock_b64, mock_img_open, MockGM):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model"
        MockGM.return_value.generate_content = MagicMock(return_value=MockGoogleGenerateContentResponse(json.dumps({"action_only": "click(G)"})))
        with patch('google.generativeai.configure'):
            result = client.analyze_and_decide("b64", "obj")
        self.assertEqual(result["thinking"], "AI response JSON (Google) missing required keys (thinking/action).")

    @patch.object(GoogleClient, '__init__', lambda self, api_key=None: None)
    @patch('google.generativeai.GenerativeModel')
    @patch('PIL.Image.open')
    @patch('base64.b64decode')
    @patch('builtins.print')
    def test_analyze_and_decide_api_error(self, mock_print, mock_b64, mock_img_open, MockGM):
        client = GoogleClient(api_key="fake_g_key"); client.default_vision_model = "v_model"
        MockGM.return_value.generate_content = MagicMock(side_effect=google_exceptions.InternalServerError("G Decide API Error"))
        with patch('google.generativeai.configure'):
            result = client.analyze_and_decide("b64", "obj")
        self.assertEqual(result["thinking"], "API call failed during decision: G Decide API Error")
        mock_print.assert_called_with("Error in analyze_and_decide with Google (model: v_model): G Decide API Error")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
```
