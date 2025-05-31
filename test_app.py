import pytest
from unittest.mock import MagicMock, patch
import app as main_app # Alias to avoid conflict if 'app' is used as a var name
import os

# Mock streamlit before it's imported by app.py
# This is a common pattern for testing streamlit apps.
@pytest.fixture(autouse=True)
def mock_streamlit(mocker):
    st_mock = MagicMock()

    # Mock st.session_state
    # Initialize session_state as a dictionary to allow attribute assignment
    st_mock.session_state = {}

    # Mock other streamlit functions used in app.py
    st_mock.sidebar = MagicMock()
    st_mock.sidebar.text_input = MagicMock(return_value="dummy_api_key")
    st_mock.sidebar.button = MagicMock(return_value=False) # Default button not clicked
    st_mock.sidebar.success = MagicMock()
    st_mock.sidebar.warning = MagicMock()
    st_mock.sidebar.error = MagicMock()
    st_mock.sidebar.divider = MagicMock()
    st_mock.sidebar.subheader = MagicMock()
    st_mock.sidebar.write = MagicMock()

    st_mock.chat_message = MagicMock()
    st_mock.chat_input = MagicMock(return_value=None) # Default no user input
    st_mock.write = MagicMock()
    st_mock.image = MagicMock()
    st_mock.info = MagicMock()
    st_mock.success = MagicMock()
    st_mock.error = MagicMock()
    st_mock.set_page_config = MagicMock()
    st_mock.title = MagicMock()
    st_mock.subheader = MagicMock()
    st_mock.columns = MagicMock(return_value=(MagicMock(), MagicMock())) # Mock two columns
    st_mock.empty = MagicMock(return_value=MagicMock()) # Mock st.empty for placeholders
    st_mock.rerun = MagicMock()

    mocker.patch.dict(main_app.st.__dict__, st_mock.__dict__)
    mocker.patch('app.st', st_mock) # Ensure app.st is this mock

    # Mock other modules used by app.py
    mocker.patch('app.BrowserAutomation', MagicMock())
    mocker.patch('app.MistralClient', MagicMock())
    mocker.patch('app.ElementDetector', MagicMock())
    mocker.patch('os.getenv', return_value=None) # Mock os.getenv

    return st_mock

def test_initialize_session_state(mock_streamlit):
    # Ensure session_state is clean before test
    mock_streamlit.session_state = {}
    main_app.initialize_session_state()

    assert 'messages' in mock_streamlit.session_state
    assert mock_streamlit.session_state.messages == []
    assert 'browser' in mock_streamlit.session_state
    assert mock_streamlit.session_state.browser is None
    assert 'mistral_client' in mock_streamlit.session_state
    assert mock_streamlit.session_state.mistral_client is None
    assert 'element_detector' in mock_streamlit.session_state
    assert isinstance(mock_streamlit.session_state.element_detector, MagicMock) # It's mocked
    assert 'automation_active' in mock_streamlit.session_state
    assert mock_streamlit.session_state.automation_active is False
    assert 'current_objective' in mock_streamlit.session_state
    assert mock_streamlit.session_state.current_objective is None

def test_setup_sidebar_api_key_handling(mock_streamlit, mocker):
    # Simulate API key input
    mock_streamlit.sidebar.text_input.return_value = "test_api_key"

    main_app.setup_sidebar()

    mock_streamlit.sidebar.text_input.assert_any_call("API Key", value="", type="password", help="Enter your Mistral AI API key")
    assert main_app.st.session_state.mistral_client is not None # Check if client was initialized
    mock_streamlit.sidebar.success.assert_called_with("✅ API Key configured")

    # Simulate no API key
    mock_streamlit.session_state.mistral_client = None # Reset
    mock_streamlit.sidebar.text_input.return_value = ""
    main_app.setup_sidebar()
    mock_streamlit.sidebar.warning.assert_called_with("⚠️ Please enter your Mistral AI API key")


def test_main_layout_and_livestream_placeholder(mock_streamlit, mocker):
    # Mock browser and automation state for livestream part
    mock_browser_active = MagicMock()
    mock_browser_active.driver = True # Simulate active driver

    mock_streamlit.session_state = {
        'messages': [],
        'browser': mock_browser_active,
        'mistral_client': MagicMock(),
        'element_detector': MagicMock(),
        'automation_active': False, # Livestream should refresh
        'current_objective': None
    }

    # Mock the take_screenshot method within the mocked browser
    mock_browser_active.take_screenshot = MagicMock(return_value="dummy_screenshot.png")

    # Mock time.sleep to prevent actual sleeping
    mocker.patch('time.sleep')

    with patch('app.update_livestream_display') as mock_update_livestream:
        main_app.main()

    # Check if columns are created
    main_app.st.columns.assert_called_with(2)
    left_col, right_col = main_app.st.columns.return_value

    # Check if livestream placeholder is created in right column
    # This depends on how st.empty is called within the column context
    # Assuming st.empty is called by the right_column mock directly or indirectly
    right_col.empty.assert_called_once()

    # Check if update_livestream_display is called when browser is active and automation is not
    # This requires careful checking of how main() calls update_livestream_display
    # In the refactored code, main calls update_livestream_display via right_column context
    # So we check if the mock_update_livestream was called by the right_column context

    # Based on the implemented logic:
    # if browser active and automation false -> update_livestream_display -> sleep -> rerun
    # We need to ensure that update_livestream_display is called
    # The actual call happens inside the `with right_column:` block
    # Let's refine this to check calls on the placeholder object returned by st.empty()

    # In the actual app, the logic is:
    # with right_column:
    #   livestream_placeholder = st.empty()
    #   if browser and browser.driver:
    #       if not automation_active:
    #           update_livestream_display(livestream_placeholder)
    #           time.sleep(1.5)
    #           st.rerun()
    #       else:
    #            update_livestream_display(livestream_placeholder) # Called once
    #   else:
    #       update_livestream_display(livestream_placeholder)

    # For the case: browser active, automation_active = False
    # mock_update_livestream should be called
    mock_update_livestream.assert_any_call(right_col.empty.return_value)
    main_app.st.rerun.assert_called_once() # Because automation is false

@patch('app.take_screenshot_and_analyze', return_value="annotated_image.png")
@patch('app.MistralClient') # Ensure we re-mock MistralClient if needed for specific tests
def test_execute_automation_step_basic_flow(mock_mistral_client_class, mock_take_screenshot, mock_streamlit):
    # Setup
    mock_streamlit.session_state.browser = MagicMock()
    mock_streamlit.session_state.browser.driver = True # Active browser
    mock_streamlit.session_state.mistral_client = MagicMock()
    mock_streamlit.session_state.mistral_client.analyze_and_decide.return_value = {
        'thinking': 'Test thinking',
        'action': 'click(1)'
    }
    mock_streamlit.session_state.current_objective = "Test objective"

    livestream_placeholder_mock = MagicMock()

    # Execute
    result = main_app.execute_automation_step("Test objective", livestream_placeholder_mock)

    # Assert
    assert result is True # Should be true if action is processed
    mock_take_screenshot.assert_called_once_with(livestream_placeholder_mock)
    main_app.st.session_state.mistral_client.analyze_and_decide.assert_called_once()
    # Check if add_message was called for thinking and action
    # This requires inspecting calls to st.info, st.success, etc. or a custom add_message mock
    # For now, let's assume add_message works if its components (st.info etc.) are called
    main_app.st.info.assert_any_call("🤔 **Thinking:** Test thinking")
    main_app.st.success.assert_any_call("⚡ **Action:** click(1)")
    main_app.st.session_state.browser.click_element_by_index.assert_called_with(1)

def test_add_message(mock_streamlit):
    main_app.st.session_state.messages = [] # Reset messages
    main_app.add_message("user", "Hello", "text")
    assert len(main_app.st.session_state.messages) == 1
    message = main_app.st.session_state.messages[0]
    assert message["role"] == "user"
    assert message["content"] == "Hello"
    assert message["type"] == "text"

# To run these tests, you would typically use `pytest test_app.py`
# Ensure that app.py can be imported (e.g., it's in PYTHONPATH or same directory)
