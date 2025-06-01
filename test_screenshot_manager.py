import os
import time
import shutil
import sys

# --- Mock Streamlit and session_state (similar to previous test file) ---
from unittest.mock import MagicMock

class MockSessionState:
    def __init__(self):
        self._data = {}

    def __contains__(self, key):
        return key in self._data

    def __getattr__(self, key):
        if key not in self._data:
            raise AttributeError(f"'{key}' not found in session_state mock")
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

# Apply the mock at the module level before importing app
sys.modules['streamlit'] = FakeStreamlitModule()
import streamlit as st # Now this should import our fake module

# --- End Mock ---

# Add current directory to sys.path to allow importing app
sys.path.append('.')
try:
    from app import manage_on_disk_screenshots, log_debug_message, MAX_SCREENSHOT_FILES
    # Initialize debug_log_messages directly for this test if not done by importing app's initialize_session_state
    if 'debug_log_messages' not in st.session_state:
        st.session_state.debug_log_messages = []
except ImportError as e:
    print(f"Failed to import from app.py: {e}")
    sys.exit(1)


SCREENSHOT_DIR_TEST = "screenshots_management_test/"
# MAX_FILES_TO_KEEP = MAX_SCREENSHOT_FILES # Use the one from app.py
MAX_FILES_TO_KEEP = 70 # Or use the value from the prompt for this specific test. Let's use the prompt's value.
NUM_FILES_TO_CREATE = 80
NUM_FILES_TO_DELETE = NUM_FILES_TO_CREATE - MAX_FILES_TO_KEEP


def run_test():
    print(f"Starting test_manage_on_disk_screenshots...")
    print(f"Screenshot directory for test: {SCREENSHOT_DIR_TEST}")
    print(f"Max files to keep: {MAX_FILES_TO_KEEP}")
    print(f"Files to create: {NUM_FILES_TO_CREATE}")
    print(f"Expected files to delete: {NUM_FILES_TO_DELETE}")

    # 1. Setup: Clean and create directory
    if os.path.exists(SCREENSHOT_DIR_TEST):
        shutil.rmtree(SCREENSHOT_DIR_TEST)
    os.makedirs(SCREENSHOT_DIR_TEST)
    print(f"Cleaned and created directory: {SCREENSHOT_DIR_TEST}")

    # 2. Create Dummy Screenshot Files
    created_file_paths = []
    print("Creating dummy files...")
    for i in range(NUM_FILES_TO_CREATE):
        filename = f"dummy_ss_{i:03d}.png"
        file_path = os.path.join(SCREENSHOT_DIR_TEST, filename)
        with open(file_path, "w") as f:
            f.write(f"dummy content {i}")
        # Touch the file to set its modification time (already done by creation, but sleep ensures order)
        os.utime(file_path, (time.time(), time.time())) # Set access and mod time
        created_file_paths.append(file_path)
        if i < NUM_FILES_TO_CREATE -1: # Avoid sleep after last file
             time.sleep(0.01) # Ensure distinct modification times

    # Get modification times for all created files to confirm order
    # This also mimics how manage_on_disk_screenshots gets them
    file_metadata = []
    for fp in created_file_paths:
        if os.path.exists(fp): # Ensure file exists before getting mtime
             file_metadata.append((fp, os.path.getmtime(fp)))

    # Sort by actual modification time to be sure of the "oldest"
    file_metadata.sort(key=lambda x: x[1])

    # Identify the oldest files that are expected to be deleted
    expected_deleted_files = [item[0] for item in file_metadata[:NUM_FILES_TO_DELETE]]
    expected_remaining_files = [item[0] for item in file_metadata[NUM_FILES_TO_DELETE:]]

    print(f"Created {len(created_file_paths)} files.")
    # print(f"Files expected to be deleted (oldest {NUM_FILES_TO_DELETE}): {expected_deleted_files}")
    # print(f"Files expected to remain (newest {MAX_FILES_TO_KEEP}): {expected_remaining_files}")


    # 3. Simulate Calling the Management Function
    print(f"Calling manage_on_disk_screenshots('{SCREENSHOT_DIR_TEST}', {MAX_FILES_TO_KEEP})...")
    manage_on_disk_screenshots(SCREENSHOT_DIR_TEST, MAX_FILES_TO_KEEP)
    print("manage_on_disk_screenshots call finished.")

    # 4. Verify Results
    print("Verifying results...")
    if not os.path.exists(SCREENSHOT_DIR_TEST):
        print(f"ERROR: Test directory {SCREENSHOT_DIR_TEST} no longer exists!")
        return False

    remaining_files_on_disk = []
    try:
        remaining_files_on_disk_names = os.listdir(SCREENSHOT_DIR_TEST)
        remaining_files_on_disk = [os.path.join(SCREENSHOT_DIR_TEST, name) for name in remaining_files_on_disk_names]
    except OSError as e:
        print(f"ERROR: Could not list directory {SCREENSHOT_DIR_TEST} after management. Reason: {e}")
        return False

    # a. Assert total number of files
    current_file_count_after_manage = len(remaining_files_on_disk)
    print(f"Files remaining on disk: {current_file_count_after_manage}")
    assert current_file_count_after_manage == MAX_FILES_TO_KEEP, \
        f"Assertion Failed: Expected {MAX_FILES_TO_KEEP} files, found {current_file_count_after_manage}"

    # b. Assert that the 10 oldest files no longer exist
    all_oldest_deleted = True
    for old_file_path in expected_deleted_files:
        if os.path.exists(old_file_path): # Check if it's still on disk
            print(f"ERROR: Oldest file '{os.path.basename(old_file_path)}' was NOT deleted.")
            all_oldest_deleted = False
    if all_oldest_deleted:
        print(f"Verified: All {NUM_FILES_TO_DELETE} oldest files were deleted.")
    else:
        print(f"FAILED: Some of the {NUM_FILES_TO_DELETE} oldest files were not deleted.")
        # For detailed debug, list which ones were not deleted:
        # remaining_old_files = [f for f in expected_deleted_files if os.path.exists(f)]
        # print(f"Not deleted old files: {[os.path.basename(f) for f in remaining_old_files]}")
        assert all_old_deleted, "Not all oldest files were deleted." # Use a generic assert True/False var

    # c. Assert that the 70 newest files still exist
    all_newest_exist = True
    for new_file_path in expected_remaining_files:
        if not os.path.exists(new_file_path): # Check if it's missing from disk
            print(f"ERROR: Newest file '{os.path.basename(new_file_path)}' is MISSING.")
            all_newest_exist = False
    if all_newest_exist:
        print(f"Verified: All {MAX_FILES_TO_KEEP} newest files still exist.")
    else:
        print(f"FAILED: Some of the {MAX_FILES_TO_KEEP} newest files are missing.")
        assert all_newest_exist, "Not all newest files exist."


    print("All assertions passed for manage_on_disk_screenshots.")
    return True

if __name__ == "__main__":
    success = False
    try:
        success = run_test()
    except AssertionError as e:
        print(f"Test Assertion Failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during the test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 5. Cleanup
        print(f"Cleaning up test directory: {SCREENSHOT_DIR_TEST}")
        if os.path.exists(SCREENSHOT_DIR_TEST):
            shutil.rmtree(SCREENSHOT_DIR_TEST)
        print("Cleanup complete.")

    if success:
        print("\n--- Test Passed ---")
    else:
        print("\n--- Test Failed ---")
        sys.exit(1) # Exit with error code if test failed
