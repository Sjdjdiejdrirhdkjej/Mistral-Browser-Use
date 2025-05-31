import sys
import os

# Add the current directory to sys.path to allow importing app
sys.path.append('.')

simulated_messages = [
    {"role": "user", "type": "text", "content": "Hello"},
    {"role": "assistant", "type": "image", "content": "screenshots/test_image1.png"},
    {"role": "assistant", "type": "text", "content": "Here is an image."},
    {"role": "user", "type": "image", "content": "screenshots/test_image2.jpg"}
]

print(f"Initial simulated_messages: {simulated_messages}")

try:
    # Attempt to import delete_screenshots from app.py
    # This part will require app.py's dependencies to be installed in the environment
    from app import delete_screenshots
    print("Successfully imported delete_screenshots from app.py")

    # 1. Execute delete_screenshots
    delete_screenshots('screenshots/')
    print("Finished calling delete_screenshots('screenshots/')")

except ImportError as e:
    print(f"Error importing delete_screenshots: {e}. Will skip file deletion for this test run.")
except Exception as e:
    print(f"An error occurred during delete_screenshots import or execution: {e}")


# 2. Apply message filtering logic
# This replicates the logic from initialize_session_state in app.py
filtered_messages = [msg for msg in simulated_messages if msg.get("type") != "image"]
simulated_messages = filtered_messages

print(f"Final simulated_messages: {simulated_messages}")

# Verify screenshot directory content by listing it (optional, can also be done by the agent)
# For now, the agent will do this as a separate step.
# if os.path.exists('screenshots'):
#     print(f"Contents of screenshots/ directory: {os.listdir('screenshots/')}")
# else:
#     print("screenshots/ directory does not exist.")
