import sys
import os
import copy # To keep a truly independent copy of initial messages

# Mock Streamlit and its session_state (same as in test_new_session.py)
class MockSessionState:
    def __init__(self):
        self._data = {}

    def __contains__(self, key):
        return key in self._data

    def __getattr__(self, key):
        if key not in self._data:
            raise AttributeError(f"'{key}' not found in session_state")
        return self._data[key]

    def __setattr__(self, key, value):
        if key == "_data":
            super().__setattr__(key, value)
        else:
            self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

class FakeStreamlitModule:
    def __init__(self):
        self.session_state = MockSessionState()

sys.modules['streamlit'] = FakeStreamlitModule()
import streamlit as st

sys.path.append('.')

initial_messages_for_active_session = [
    {"role": "assistant", "type": "image", "content": "screenshots/active_test.png"},
    {"role": "user", "type": "text", "content": "Hello"}
]

# Pre-populate session_state to simulate an active session
st.session_state.messages = copy.deepcopy(initial_messages_for_active_session)

try:
    from app import initialize_session_state, delete_screenshots # delete_screenshots import not strictly needed here but good for consistency
    print("Successfully imported functions from app.py")

    print(f"Before initialize_session_state, 'messages' in st.session_state: {'messages' in st.session_state}")
    print(f"Initial st.session_state.messages: {st.session_state.messages}")

    # Call the actual initialize_session_state from app.py
    initialize_session_state()
    print("Called initialize_session_state()")

    print(f"After initialize_session_state, st.session_state.messages: {st.session_state.messages}")

    # Verification
    if st.session_state.messages == initial_messages_for_active_session:
        print("Test Active Session: Message state VERIFIED: messages list is unchanged.")
    else:
        print("Test Active Session: Message state FAILED: messages list has changed.")
        print(f"Expected: {initial_messages_for_active_session}")
        print(f"Got: {st.session_state.messages}")

except ImportError as e:
    print(f"ImportError: {e}. Ensure app.py and its dependencies are accessible.")
except Exception as e:
    print(f"An error occurred: {e}")

print("\nTest Active Session: Check screenshot file (should NOT be deleted by agent's ls call next)")
