import pytest
from unittest.mock import patch, MagicMock
from mistral_client import MistralClient # Assuming it's in mistral_client.py
import json # For comparing JSON payloads

@pytest.fixture
def mistral_client_instance():
    return MistralClient(api_key="test_api_key")

def test_mistral_client_initialization(mistral_client_instance):
    assert mistral_client_instance.api_key == "test_api_key"
    assert mistral_client_instance.api_url == "https://api.mistral.ai/v1/chat/completions"

@patch('requests.post') # Assuming MistralClient uses requests.post
def test_analyze_and_decide_success(mock_post, mistral_client_instance):
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Example response structure from Mistral AI - adjust if necessary
    expected_response_data = {
        "choices": [{
            "message": {
                "content": json.dumps({"thinking": "Test thought", "action": "Test action"})
            }
        }]
    }
    mock_response.json.return_value = expected_response_data
    mock_post.return_value = mock_response

    image_data = "base64_encoded_image_data"
    user_objective = "Test objective"
    current_task_context = "Test context"

    result = mistral_client_instance.analyze_and_decide(image_data, user_objective, current_task_context)

    # Check that requests.post was called correctly
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == mistral_client_instance.api_url # Check URL

    # Check headers
    expected_headers = {
        "Authorization": f"Bearer {mistral_client_instance.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    assert kwargs['headers'] == expected_headers

    # Check payload (messages structure)
    payload = kwargs['json']
    assert payload['model'] == "mistral-large-latest" # or "mistral-small-latest" depending on client
    assert len(payload['messages']) == 2 # System and User message

    # Check system message (prompt)
    assert "You are an expert web automation assistant." in payload['messages'][0]['content']

    # Check user message content
    user_message_content = payload['messages'][1]['content']
    assert isinstance(user_message_content, list)
    assert user_message_content[0]['type'] == "text"
    assert user_objective in user_message_content[0]['text']
    assert current_task_context in user_message_content[0]['text']
    assert user_message_content[1]['type'] == "image_url"
    assert user_message_content[1]['image_url']['url'].startswith("data:image/png;base64,")
    assert user_message_content[1]['image_url']['url'].endswith(image_data)

    assert payload['temperature'] == 0.3
    assert payload['max_tokens'] == 200
    assert 'json.tool_choice' not in payload # Assuming no tools for this specific call based on current understanding

    # Check that the result is parsed correctly
    assert result == {"thinking": "Test thought", "action": "Test action"}

@patch('requests.post')
def test_analyze_and_decide_api_error(mock_post, mistral_client_instance):
    # Mock API error response
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response

    with pytest.raises(Exception) as excinfo:
        mistral_client_instance.analyze_and_decide("img_data", "obj", "ctx")

    assert "API request failed with status 400" in str(excinfo.value)
    assert "Bad Request" in str(excinfo.value)

@patch('requests.post')
def test_analyze_and_decide_json_decode_error(mock_post, mistral_client_instance):
    # Mock successful status but malformed JSON in response content
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Simulate malformed JSON in the 'content' field of the choice
    malformed_content = "this is not valid json"
    mock_response.json.return_value = {
        "choices": [{"message": {"content": malformed_content}}]
    }
    mock_post.return_value = mock_response

    with pytest.raises(json.JSONDecodeError): # Or a more specific custom exception if client wraps it
        mistral_client_instance.analyze_and_decide("img_data", "obj", "ctx")

@patch('requests.post')
def test_analyze_and_decide_unexpected_response_structure(mock_post, mistral_client_instance):
    # Mock successful status but unexpected JSON structure
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Simulate missing 'choices' or other key parts
    mock_response.json.return_value = {"error": "Unexpected structure"}
    mock_post.return_value = mock_response

    with pytest.raises(Exception): # Expecting a KeyError or custom error
        mistral_client_instance.analyze_and_decide("img_data", "obj", "ctx")

# Note: If MistralClient uses a different HTTP library (e.g., httpx),
# the @patch target needs to be adjusted accordingly (e.g., @patch('httpx.post')).
# The prompt content and payload structure should also match what MistralClient actually sends.
