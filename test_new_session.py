import sys
import os

# Mock Streamlit and its session_state
class MockSessionState:
    def __init__(self):
        self._data = {}

    def __contains__(self, key):
        return key in self._data

    def __getattr__(self, key):
        if key not in self._data:
            # Streamlit's session_state would raise AttributeError if key doesn't exist
            # and it's not accessed via get() or __contains__
            raise AttributeError(f"'{key}' not found in session_state")
        return self._data[key]

    def __setattr__(self, key, value):
        if key == "_data":
            super().__setattr__(key, value)
        else:
            self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

# Create a fake streamlit module and session_state instance
class FakeStreamlitModule:
    def __init__(self):
        self.session_state = MockSessionState()

sys.modules['streamlit'] = FakeStreamlitModule()
import streamlit as st # Now this should import our fake module

# Add current directory to sys.path to allow importing app
sys.path.append('.')

try:
    from app import initialize_session_state, delete_screenshots
    print("Successfully imported functions from app.py")

    # Ensure session_state is 'new' (messages not in it)
    # Our MockSessionState starts empty, so 'messages' is not in st.session_state initially.
    print(f"Before initialize_session_state, 'messages' in st.session_state: {'messages' in st.session_state}")

    # Call the actual initialize_session_state from app.py
    initialize_session_state()
    print("Called initialize_session_state()")

    print(f"After initialize_session_state, 'messages' in st.session_state: {'messages' in st.session_state}")
    if 'messages' in st.session_state:
        print(f"st.session_state.messages: {st.session_state.messages}")
    else:
        print("st.session_state.messages was not initialized.")

except ImportError as e:
    print(f"ImportError: {e}. Ensure app.py and its dependencies are accessible.")
    print("This test requires app.py to be importable and its dependencies (like selenium, cv2 etc.) to be installed if they are imported at module level.")
except Exception as e:
    print(f"An error occurred: {e}")

print("\nTest New Session: Check screenshot files (should be deleted by agent's ls call next)")
print(f"Test New Session: messages content: {st.session_state.messages if 'messages' in st.session_state else 'Not initialized'}")

if 'messages' in st.session_state and st.session_state.messages == []:
    print("Test New Session: Message state VERIFIED: messages is empty list.")
else:
    print("Test New Session: Message state FAILED: messages is not an empty list or not found.")

# The agent will use ls("screenshots/") to verify file deletion.
