import os
import shutil
import pytest
from unittest.mock import MagicMock # For a simpler mock if mocker gets complex for streamlit module
import app # Import the app module itself

# Attempt to import functions from app.py
# These imports assume app.py is in the same directory or PYTHONPATH is set up
# We will also need to mock 'streamlit' as it's imported in app.py
# from app import initialize_session_state, delete_screenshots, add_message
# No longer need to import them individually if we use app.function_name

SCREENSHOT_DIR = "screenshots_pytest_temp/"

@pytest.fixture
def mock_st_session_state(mocker):
    """
    Fixture to mock streamlit.session_state.
    It patches 'app.st' assuming app.py uses 'import streamlit as st'.
    """
    # Create a dictionary-like object to simulate session_state
    _session_state_dict = {}

    class MockSessionState:
        def __init__(self, _dict):
            self._data = _dict

        def __contains__(self, key):
            return key in self._data

        def __getattr__(self, key):
            if key not in self._data:
                raise AttributeError(f"'{key}' not found in session_state mock")
            return self._data[key]

        def __setattr__(self, key, value):
            if key == "_data":
                super().__setattr__(key, value) # Allow setting internal _data
            else:
                self._data[key] = value

        def get(self, key, default=None):
            return self._data.get(key, default)

    mock_ss = MockSessionState(_session_state_dict)

    # If app.py does "import streamlit as st", then we mock "app.st.session_state"
    # We might need to mock the entire 'streamlit' module if 'st' itself is used for other things
    mock_streamlit_module = MagicMock()
    mock_streamlit_module.session_state = mock_ss

    mocker.patch('app.st', mock_streamlit_module, create=True)
    return mock_ss


@pytest.fixture
def screenshots_test_dir():
    """
    Pytest fixture to create and clean up a dummy screenshots directory for tests.
    """
    if os.path.exists(SCREENSHOT_DIR):
        shutil.rmtree(SCREENSHOT_DIR)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    # Override the default screenshots directory in app.py for the duration of the test
    # This requires delete_screenshots and add_message to use this path.
    # For simplicity in this test, we'll ensure functions are called with this path.
    # If app.py hardcodes 'screenshots/', that's a different challenge.
    # The current delete_screenshots takes a path, so that's good.
    # add_message's image content is just a string, so it's fine.
    yield SCREENSHOT_DIR
    shutil.rmtree(SCREENSHOT_DIR)


def test_screenshot_persistence_across_reruns(mock_st_session_state, screenshots_test_dir, capsys):
    """
    Tests that screenshots and their corresponding chat messages persist across simulated
    Streamlit reruns once a session is established.
    """
    # Ensure app.delete_screenshots uses our test directory if it's called
    # This is implicitly handled by passing screenshots_test_dir to delete_screenshots if needed,
    # or if initialize_session_state internally calls delete_screenshots('screenshots/'),
    # we might need to patch that default path or the function itself.
    # For this test, the key is that initialize_session_state uses the mocked session_state.

    # Patch app.delete_screenshots to use the test directory and to avoid issues if
    # it tries to print using st.add_message which we are not fully mocking here.
    original_delete_screenshots = app.delete_screenshots
    def patched_delete_screenshots(path):
        if path == 'screenshots/': # Default path in app.py
             original_delete_screenshots(screenshots_test_dir) # Redirect to test dir
        else:
            original_delete_screenshots(path) # Call normally if another path is given

    app.delete_screenshots = patched_delete_screenshots


    # a. Initial Setup (handled by fixtures)
    # mock_st_session_state is empty here

    # b. Simulate First Run (New Session)
    # initialize_session_state will use the mocked and patched app.st.session_state
    app.initialize_session_state()
    captured_new_session = capsys.readouterr()
    assert "DEBUG: 'messages' not in st.session_state" in captured_new_session.out
    assert mock_st_session_state.messages == []

    # c. Simulate Taking a Screenshot
    dummy_screenshot_filename = "test_image1.png"
    dummy_screenshot_path = os.path.join(screenshots_test_dir, dummy_screenshot_filename)

    with open(dummy_screenshot_path, "w") as f:
        f.write("dummy image data")
    assert os.path.exists(dummy_screenshot_path)

    # add_message appends to the mocked st.session_state.messages
    app.add_message("assistant", dummy_screenshot_path, "image")
    assert len(mock_st_session_state.messages) == 1
    assert mock_st_session_state.messages[0]["type"] == "image"
    assert mock_st_session_state.messages[0]["content"] == dummy_screenshot_path

    # d. Simulate a Script Rerun
    # 'messages' is now in mock_st_session_state
    app.initialize_session_state()
    captured_active_session = capsys.readouterr()
    assert "DEBUG: 'messages' found in st.session_state" in captured_active_session.out

    # e. Assert Persistence
    assert os.path.exists(dummy_screenshot_path), "Screenshot file should still exist after rerun"
    assert len(mock_st_session_state.messages) == 1, "Messages list should still have one message"
    assert mock_st_session_state.messages[0]["type"] == "image", "Image message should persist"
    assert mock_st_session_state.messages[0]["content"] == dummy_screenshot_path, "Image message content should persist"

    # Restore original delete_screenshots if other tests use it
    app.delete_screenshots = original_delete_screenshots
