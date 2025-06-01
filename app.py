import streamlit as st
import os
# import shutil # Removed as it's no longer used
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
from mistral_client import MistralClient
from element_detector import ElementDetector
import todo_manager # Added import
import traceback
import re # Added import

# Max number of debug messages to keep in session state (REMOVED)
# MAX_DEBUG_MESSAGES = 100 (REMOVED)
MAX_EXECUTION_SUMMARY_ITEMS = 20 # Cap for execution_summary
MAX_CHAT_MESSAGES = 50 # Cap for chat messages
# MAX_SCREENSHOT_FILES = 70 (REMOVED)

# All functions log_debug_message, delete_screenshots, manage_on_disk_screenshots, get_current_screenshot_file_count are removed.

def get_current_screenshot_file_count(directory: str = "screenshots/") -> int:
    """Counts the number of files in the specified directory."""
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' not found or invalid for get_current_screenshot_file_count.")
        return 0

    count = 0
    try:
        for entry_name in os.listdir(directory):
            full_path = os.path.join(directory, entry_name)
            if os.path.isfile(full_path):
                count += 1
    except OSError as e:
        print(f"Error listing directory '{directory}' for count: {e}")
        return 0 # Return 0 as count is unreliable or directory became inaccessible
    return count

def clear_screenshots_directory_and_history(directory: str = "screenshots/"):
    """
    Deletes all files in the specified screenshot directory and clears image messages from chat history.
    """
    # Clear directory
    if not os.path.isdir(directory):
        add_message("assistant", f"Error: Screenshot directory '{directory}' not found.", "error")
        # No need to clear image messages if the primary action (dir clearing) has an issue with dir existence.
        return

    deleted_files_count = 0
    failed_files_count = 0

    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    deleted_files_count += 1
                except Exception as e_remove:
                    failed_files_count += 1
                    print(f"Error deleting file {file_path}: {e_remove}") # Log to console for server-side debug

        if deleted_files_count > 0:
            add_message("assistant", f"Successfully deleted {deleted_files_count} screenshot(s) from '{directory}'.", "info")
        elif failed_files_count == 0 and deleted_files_count == 0: # No files to delete and no failures
            add_message("assistant", f"Screenshot directory '{directory}' was already empty.", "info")

        if failed_files_count > 0:
            add_message("assistant", f"Failed to delete {failed_files_count} file(s) from '{directory}'. Check server logs.", "error")

    except OSError as e_list:
        add_message("assistant", f"Error accessing screenshot directory '{directory}': {e_list}", "error")
        # Proceed to clear history even if directory access failed, as they are separate concerns.

    # Clear image messages from chat history
    if 'messages' in st.session_state:
        initial_message_count = len(st.session_state.messages)
        st.session_state.messages = [msg for msg in st.session_state.messages if msg.get("type") != "image"]
        messages_cleared_count = initial_message_count - len(st.session_state.messages)
        if messages_cleared_count > 0:
            add_message("assistant", f"{messages_cleared_count} image message(s) cleared from chat history.", "info")
        elif deleted_files_count == 0 and failed_files_count == 0: # If dir was empty, and no image messages
             pass # Avoid redundant "no image messages" if dir was also empty.
        else: # If dir had files, or errors, but no image messages
            add_message("assistant", "No image messages found in chat history to clear.", "info")


def initialize_session_state():
    """Initialize session state variables"""
    # if 'debug_log_messages' not in st.session_state: (REMOVED)
    #     st.session_state.debug_log_messages = [] (REMOVED)

    # This block now handles initialization for a truly new session
    if 'messages' not in st.session_state:
        # log_debug_message("DEBUG_STATE: 'messages' not in st.session_state. Initializing 'messages' as new empty list.") (REMOVED)
        # delete_screenshots('screenshots/') # Removed as per instruction (ALREADY REMOVED)
        st.session_state.messages = [] # Initialize empty messages list
        # Image messages would be empty at this point, so filtering is nominal
        # but kept for logical consistency if messages were ever pre-populated by other means
        # in a "new session" context before this specific line.
        # No need to filter an empty list: st.session_state.messages = [msg for msg in st.session_state.messages if msg.get("type") != "image"]
        # Initialize other 'new session' specific variables here if needed
    # else: (REMOVED log_debug_message call from here too)
        # log_debug_message("DEBUG_STATE: 'messages' found in st.session_state. Active session detected. Screenshot deletion and image message clearing will be skipped.") (REMOVED)

    # Initialize other session state variables if they don't exist
    # These might be initialized on first run or if they were cleared somehow,
    # but not necessarily tied to the 'messages' key as a new session indicator.
    if 'execution_mode' not in st.session_state:
        st.session_state.execution_mode = "Browser Use"
    if 'browser' not in st.session_state:
        st.session_state.browser = None
    if 'mistral_client' not in st.session_state:
        st.session_state.mistral_client = None
    if 'element_detector' not in st.session_state:
        st.session_state.element_detector = ElementDetector()
    if 'automation_active' not in st.session_state:
        st.session_state.automation_active = False
    if 'current_objective' not in st.session_state:
        st.session_state.current_objective = None
    if 'step_count' not in st.session_state: # Add this check
        st.session_state.step_count = 0    # Add this line
    # New orchestrator and todo state variables
    if 'todo_objective' not in st.session_state:
        st.session_state.todo_objective = None
    if 'todo_tasks' not in st.session_state:
        st.session_state.todo_tasks = []
    if 'orchestrator_active' not in st.session_state:
        st.session_state.orchestrator_active = False
    if 'current_task_index' not in st.session_state:
        st.session_state.current_task_index = 0
    if 'execution_summary' not in st.session_state:
        st.session_state.execution_summary = []
    if 'planning_requested' not in st.session_state:
        st.session_state.planning_requested = False
    if 'user_input_for_planning' not in st.session_state:
        st.session_state.user_input_for_planning = None
    

def setup_sidebar():
    """Setup sidebar for API key configuration and controls"""
    st.sidebar.title("🔧 Configuration")
    
    # API Key Configuration
    st.sidebar.subheader("Mistral AI API Key")
    api_key = st.sidebar.text_input(
        "API Key", 
        value=os.getenv("MISTRAL_API_KEY", ""),
        type="password",
        help="Enter your Mistral AI API key"
    )
    
    if api_key:
        if st.session_state.mistral_client is None or st.session_state.mistral_client.api_key != api_key:
            st.session_state.mistral_client = MistralClient(api_key)
            st.sidebar.success("✅ API Key configured")
    else:
        st.sidebar.warning("⚠️ Please enter your Mistral AI API key")
    
    st.sidebar.divider()

    st.sidebar.subheader("Execution Mode")
    st.radio(
        label="Select Mode",
        options=("Browser Use", "E2B Desktop Computer Use"),
        key='execution_mode',
        # The default value is implicitly handled by st.session_state.execution_mode
    )
    # No divider after radio, "Browser Controls" has one before it.
    
    # Browser Controls
    st.sidebar.subheader("Browser Controls")
    
    if st.sidebar.button("🚀 Start Browser", disabled=st.session_state.automation_active):
        if st.session_state.execution_mode == "Browser Use":
            try:
                st.session_state.browser = BrowserAutomation()
                st.session_state.browser.start_browser()
                st.sidebar.success("✅ Browser started")
                # automation_active is typically set by the browser start success
            except Exception as e:
                st.sidebar.error(f"❌ Failed to start browser: {str(e)}")
        elif st.session_state.execution_mode == "E2B Desktop Computer Use":
            st.sidebar.info("E2B Desktop mode selected. Manual start from E2B environment expected.")
            # For E2B, we might not set st.session_state.browser or automation_active here.
            # These could be set by a callback or a different mechanism once E2B confirms connection.
    
    if st.sidebar.button("🛑 Stop Browser", disabled=not st.session_state.automation_active):
        if st.session_state.execution_mode == "Browser Use":
            try:
                if st.session_state.browser:
                    st.session_state.browser.close()
                    st.session_state.browser = None
                    st.session_state.automation_active = False # Reset for Browser Use mode
                st.sidebar.success("✅ Browser stopped")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to stop browser: {str(e)}")
        elif st.session_state.execution_mode == "E2B Desktop Computer Use":
            st.sidebar.info("E2B Desktop mode. Manual stop from E2B environment expected.")
            st.session_state.browser = None # Ensure browser object is cleared
            st.session_state.automation_active = False # Reset automation_active
    
    # Status indicators
    st.sidebar.divider()
    st.sidebar.subheader("Status")
    
    browser_status = "🟢 Running" if st.session_state.browser and st.session_state.automation_active else "🔴 Stopped"
    st.sidebar.write(f"Browser: {browser_status}")
    
    api_status = "🟢 Connected" if st.session_state.mistral_client else "🔴 Not configured"
    st.sidebar.write(f"Mistral AI: {api_status}")

    # Debug Log Expander and Screenshot Count Display REMOVED from sidebar

    st.sidebar.divider()
    current_file_count = get_current_screenshot_file_count() # Uses default "screenshots/"
    st.sidebar.caption(f"On-disk Screenshots: {current_file_count}")

    st.sidebar.divider()
    st.sidebar.subheader("Screenshot Management")
    if st.sidebar.button("⚠️ Delete All Screenshots Now"):
        clear_screenshots_directory_and_history() # Uses default "screenshots/"
        st.rerun()

def display_chat_history():
    """Display chat message history"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["type"] == "text":
                st.write(message["content"])
            elif message["type"] == "image":
                st.image(message["content"], caption=message.get("caption", "Screenshot"))
            elif message["type"] == "thinking":
                st.info(f"🤔 **Thinking:** {message['content']}")
            elif message["type"] == "action":
                st.success(f"⚡ **Action:** {message['content']}")
            elif message["type"] == "error":
                st.error(f"❌ **Error:** {message['content']}")
            elif message["type"] == "plan": # For displaying To-Do plan
                st.markdown(message["content"])
            elif message["type"] == "info": # For general info messages from orchestrator
                st.info(f"ℹ️ {message['content']}")
            elif message["type"] == "success": # For success messages
                st.success(f"✅ {message['content']}")


def add_message(role, content, msg_type="text", caption=None):
    """Add a message to chat history"""
    message = {
        "role": role,
        "type": msg_type,
        "content": content,
        "timestamp": datetime.now()
    }
    if caption:
        message["caption"] = caption
    st.session_state.messages.append(message)

    # Cap the chat messages list
    if len(st.session_state.messages) > MAX_CHAT_MESSAGES:
        st.session_state.messages = st.session_state.messages[-MAX_CHAT_MESSAGES:]

def take_screenshot_and_analyze():
    """Take screenshot and analyze with element detection"""
    if st.session_state.execution_mode == "Browser Use":
        try:
            if not st.session_state.browser:
                raise Exception("Browser not started")

            # Take screenshot
            screenshot_path = st.session_state.browser.take_screenshot()
            add_message("assistant", screenshot_path, "image", "Current page screenshot")

            # Detect and highlight elements
            annotated_image_path = st.session_state.element_detector.detect_and_annotate_elements(screenshot_path, st.session_state.browser)
            add_message("assistant", annotated_image_path, "image", "Elements detected and indexed")

            return annotated_image_path

        except Exception as e:
            error_msg = f"Failed to take screenshot: {str(e)}"
            add_message("assistant", error_msg, "error")
            return None
    elif st.session_state.execution_mode == "E2B Desktop Computer Use":
        add_message("assistant", "Screenshot functionality for E2B mode is not yet implemented.", "info")
        # For now, we can return a placeholder or None.
        # If a placeholder image is desired:
        # placeholder_path = "path/to/your/e2b_placeholder_image.png"
        # if os.path.exists(placeholder_path):
        #     add_message("assistant", placeholder_path, "image", "E2B Mode Active - No Preview")
        #     return placeholder_path
        # else:
        #     add_message("assistant", "E2B placeholder image not found.", "error")
        #     return None
        return None

def execute_browser_action(action_str: str) -> bool:
    """
    Executes a browser action string (e.g., click, type, press_key).
    Returns True if the action was attempted, False on format error or immediate failure.
    """
    if st.session_state.execution_mode == "Browser Use":
        try:
            if not st.session_state.browser:
                add_message("assistant", "Browser not available to execute action.", "error")
                return False

            action_str_lower = action_str.lower()
        if action_str_lower.startswith('click('):
            match = re.search(r"click\((\d+)\)", action_str_lower)
            if match:
                index = int(match.group(1))
                st.session_state.browser.click_element_by_index(index)
                add_message("assistant", f"Clicked element at index {index}", "action") # Changed type to "action"
                return True
            else:
                raise ValueError(f"Invalid click action format: {action_str}")
        
        elif action_str_lower.startswith('type('):
            match = re.search(r"type\(['\"](.*?)['\"]\s*,\s*into\s*=\s*['\"](.*?)['\"]\)", action_str, re.IGNORECASE)
            if match:
                text_to_type = match.group(1)
                element_description = match.group(2)
                st.session_state.browser.type_text(text_to_type, element_description)
                add_message("assistant", f"Typed '{text_to_type}' into '{element_description}'", "action")
                return True
            else:
                raise ValueError(f"Invalid type action format: {action_str}")

        elif action_str_lower.startswith('press_key('):
            match = re.search(r"press_key\(['\"](.*?)['\"]\)", action_str_lower)
            if match:
                key_name = match.group(1).lower()
                # Add validation for supported keys if necessary
                supported_keys = ["enter", "escape", "tab"]
                if key_name not in supported_keys:
                    raise ValueError(f"Unsupported key: {key_name}. Supported keys are: {supported_keys}")
                st.session_state.browser.press_key(key_name)
                add_message("assistant", f"Pressed key: {key_name}", "action")
                return True
            else:
                raise ValueError(f"Invalid press_key action format: {action_str}")

        elif action_str_lower.startswith('navigate_to('):
            match = re.search(r"navigate_to\(([^)]+)\)", action_str, re.IGNORECASE)
            if match:
                url_with_quotes = match.group(1)
                url_to_navigate = url_with_quotes.strip("'\"") # Correctly strips single and double quotes

                if not url_to_navigate:
                    add_message("assistant", f"Could not extract URL from navigate_to action (after stripping): {action_str}", "error")
                    return False

                # Basic URL validation (starts with http or https)
                if not (url_to_navigate.startswith("http://") or url_to_navigate.startswith("https://")):
                    add_message("assistant", f"Invalid URL format for navigation: {url_to_navigate}. Must start with http:// or https://", "error")
                    return False

                add_message("assistant", f"Navigating to: {url_to_navigate}", "action")
                try:
                    st.session_state.browser.navigate_to(url_to_navigate)
                    add_message("assistant", f"Successfully navigated to {url_to_navigate}", "success")
                    return True
                except Exception as e:
                    error_msg = f"Failed to navigate to {url_to_navigate}: {str(e)}"
                    add_message("assistant", error_msg, "error")
                    return False
            else:
                add_message("assistant", f"Invalid navigate_to action format: {action_str}", "error")
                return False
        
        elif 'complete' in action_str_lower or 'done' in action_str_lower:
            add_message("assistant", "Completion signal received.", "action")
            return True
        
        else:
            add_message("assistant", f"Unknown or malformed action: {action_str}", "error")
            return False

        except Exception as e:
            error_msg = f"Error executing action '{action_str}': {str(e)}"
            add_message("assistant", error_msg, "error")
            return False
    elif st.session_state.execution_mode == "E2B Desktop Computer Use":
        add_message("assistant", f"Action '{action_str}' for E2B mode is not yet implemented.", "info")
        # Depending on how E2B actions are confirmed, this might return True if the message is sent to E2B,
        # or False if it's purely a placeholder for now.
        return False # Placeholder behavior: action not truly executed by this app.

# Note: The old execute_automation_step is removed as its logic is refactored or moved.

def main():
    """Main application function"""
    st.set_page_config(
        page_title="Web Automation Assistant",
        page_icon="🤖",
        layout="wide"
    )
    
    # Log messages after st.set_page_config, as it must be the first Streamlit command.
    # log_debug_message itself ensures 'debug_log_messages' is initialized in session_state.
    # log_debug_message(f"DEBUG_STATE: In main(), AFTER st.set_page_config(), 'messages' in session_state: {'messages' in st.session_state}") # REMOVED

    st.title("Mistral Browser Use")
    st.subheader("Powered by Mistral AI & Computer Vision")
    
    initialize_session_state() # Initializes 'messages' and other states.
    setup_sidebar()
    
    # Main chat interface
    st.write("Enter your automation objective and I'll help you navigate the web!")
    
    # Display chat history
    display_chat_history()
    
    # User input
    user_input = st.chat_input("What would you like me to do on the web?", disabled=st.session_state.get('orchestrator_active', False))
    
    if user_input:
        add_message("user", user_input)
        
        # Check prerequisites
        if not st.session_state.mistral_client:
            add_message("assistant", "Please configure your Mistral AI API key in the sidebar first.", "error")
            # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at API key prerequisite failed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
            st.rerun()
            return
        
        if st.session_state.execution_mode == "E2B Desktop Computer Use":
            add_message("assistant", "E2B Desktop Computer Use mode is active. Ensure your E2B environment is ready.", "info")
            # In E2B mode, we might not strictly need st.session_state.browser to be set by *this* app's "Start Browser"
            # The E2B environment itself might provide the browser or equivalent.
        elif st.session_state.execution_mode == "Browser Use" and not st.session_state.browser:
            add_message("assistant", "Please start the browser first using the sidebar controls.", "error")
            st.rerun()
            return

        # Set flags for planning and store the input
        st.session_state.user_input_for_planning = user_input
        st.session_state.planning_requested = True

        # Reset orchestrator state for a new objective
        st.session_state.orchestrator_active = False
        st.session_state.todo_tasks = []
        st.session_state.current_task_index = 0
        st.session_state.execution_summary = []
        # current_objective will be set once planning is complete from user_input_for_planning

        # log_debug_message(f"DEBUG_STATE: Just before st.rerun() after setting planning_requested, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
        st.rerun()

    # New block to handle planning if requested
    if st.session_state.get('planning_requested'):
        # log_debug_message(f"DEBUG_STATE: Entered planning_requested block, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
        # Consume the event
        st.session_state.planning_requested = False
        current_objective_for_planning = st.session_state.user_input_for_planning
        st.session_state.user_input_for_planning = None # Clear it after use

        # Initialize orchestrator flags
        st.session_state.current_objective = current_objective_for_planning
        # orchestrator_active will be set to True only after successful planning
        st.session_state.automation_active = False # Ensure legacy automation is off
        st.session_state.current_task_index = 0
        st.session_state.execution_summary = []

        add_message("assistant", f"Received new objective: {current_objective_for_planning}. Initializing orchestrator and planning steps...")
        
        todo_manager.reset_todo_file(current_objective_for_planning)
        add_message("assistant", f"📝 `todo.md` reset for objective: {current_objective_for_planning}", "info")

        try:
            if not st.session_state.mistral_client: # This check is also in user_input, but good for safety
                add_message("assistant", "Mistral client not initialized. Cannot generate steps.", "error")
                # log_debug_message(f"DEBUG_STATE: Just before st.rerun() in planning_requested (Mistral client error), 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
                st.rerun()
                return

            add_message("assistant", "🧠 Generating steps with pixtral-large-latest...", "info")
            # log_debug_message(f"DEBUG_MSG: Generating steps with pixtral-large-latest for objective: {current_objective_for_planning}") # REMOVED

            generated_steps = st.session_state.mistral_client.generate_steps_for_todo(
                user_prompt=current_objective_for_planning,
                model_name="pixtral-large-latest"
            )

            if not generated_steps:
                add_message("assistant", "⚠️ Failed to generate steps or no steps were returned. Please try rephrasing your objective.", "error")
                # log_debug_message(f"DEBUG_STATE: Just before st.rerun() in planning_requested (no steps generated), 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
                st.rerun()
                return

            add_message("assistant", f"✅ Steps generated: {len(generated_steps)} steps.", "success")
            # log_debug_message(f"DEBUG_MSG: Steps generated: {len(generated_steps)} steps.") # REMOVED

            todo_manager.create_todo_file(current_objective_for_planning, generated_steps)
            add_message("assistant", "💾 `todo.md` populated with generated steps.", "info")
            # log_debug_message(f"DEBUG_MSG: todo.md populated with generated steps.") # REMOVED

            retrieved_todo = todo_manager.read_todo_file()
            st.session_state.todo_objective = retrieved_todo.get("objective") # Should match current_objective_for_planning
            st.session_state.todo_tasks = retrieved_todo.get("tasks", [])
            st.session_state.current_task_index = 0

            plan_display_intro = "**Planning Agent (Pixtral-Large-Latest) says:** Planning complete. Here's the initial plan:"
            plan_display = f"{plan_display_intro}\n\n**Objective:** {st.session_state.todo_objective}\n\n"
            plan_display += "**Tasks:**\n"
            if st.session_state.todo_tasks:
                for i, task_item in enumerate(st.session_state.todo_tasks):
                    plan_display += f"- [ ] {task_item} \n"
            else:
                plan_display += "- No tasks defined yet."
            add_message("assistant", plan_display, "plan")

            st.session_state.orchestrator_active = True # Activate orchestrator only after successful planning

        except Exception as e:
            error_msg = f"Error during planning phase: {str(e)}\n{traceback.format_exc()}"
            add_message("assistant", error_msg, "error")
            st.session_state.orchestrator_active = False # Ensure orchestrator is not active on error

        # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at end of planning_requested block, orchestrator_active: {st.session_state.orchestrator_active}, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
        st.rerun()

    # Orchestrator Main Execution Loop
    if st.session_state.get('orchestrator_active') and st.session_state.todo_tasks:
        if not st.session_state.browser or not st.session_state.mistral_client: # This check is also in user_input, but good for safety if state changes
            add_message("assistant", "Browser or Mistral client not initialized. Orchestrator cannot proceed.", "error")
            st.session_state.orchestrator_active = False
            # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at orchestrator prerequisites failed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
            st.rerun()
            return

        task_idx = st.session_state.current_task_index
        tasks = st.session_state.todo_tasks

        if task_idx < len(tasks):
            current_task = tasks[task_idx]
            add_message("assistant", f"🚀 Executing Task {task_idx + 1}/{len(tasks)}: {current_task}", "info")

            # A. Action Execution (using pixtral-large-latest for analyze_and_decide)
            add_message("assistant", "🤔 Thinking on how to execute the current task...", "thinking")
            annotated_image_path = take_screenshot_and_analyze()

            if not annotated_image_path:
                add_message("assistant", "Failed to get screenshot for action decision. Stopping.", "error")
                st.session_state.orchestrator_active = False
                # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at orchestrator action screenshot failed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
                st.rerun()
                return

            try:
                with open(annotated_image_path, 'rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')

                # Model for determining browser actions: pixtral-large-2411
                action_decision_model = "pixtral-large-2411"
                # For current_objective, pass the overall objective to give context to analyze_and_decide
                response = st.session_state.mistral_client.analyze_and_decide(
                    image_data, current_task, model_name=action_decision_model, current_context=st.session_state.todo_objective
                )

                thinking = response.get('thinking', 'No reasoning provided for action.')
                action_str = response.get('action', '')
                add_message("assistant", f"**Action Model (Pixtral-Large-2411) Reasoning:** {thinking}", "thinking")

                if not action_str:
                    add_message("assistant", "No action could be determined. Trying task again or may need replan.", "error")
                    # Potentially increment a retry counter for the task or stop
                    st.session_state.execution_summary.append({"task": current_task, "action_model_response": response, "status": "No action determined"})
                    if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                        st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]
                    # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at orchestrator no action determined, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
                    st.rerun() # Re-run, might try same task if index not incremented
                    return

                action_executed_successfully = execute_browser_action(action_str)
                st.session_state.execution_summary.append({"task": current_task, "action": action_str, "executed": action_executed_successfully})
                if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                    st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]

                if not action_executed_successfully and action_str.lower() not in ['complete', 'done']:
                     add_message("assistant", f"Action '{action_str}' failed to execute properly. Will re-evaluate.", "error")
                     # Re-run will happen, and the same task will be picked up. analyze_state_vision will assess new state.

            except Exception as e:
                add_message("assistant", f"Error during action execution phase: {str(e)}\n{traceback.format_exc()}", "error")
                st.session_state.orchestrator_active = False
                # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at orchestrator action execution error, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
                st.rerun()
                return

            # B. State Analysis (using pixtral-large-latest for analyze_state_vision)
            add_message("assistant", "🧐 Analyzing outcome of the action...", "info")
            time.sleep(1) # Brief pause for page to potentially update after action
            annotated_image_path_after_action = take_screenshot_and_analyze()

            if not annotated_image_path_after_action:
                add_message("assistant", "Failed to get screenshot for state analysis. Stopping.", "error")
                st.session_state.orchestrator_active = False
                # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at orchestrator state analysis screenshot failed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
                st.rerun()
                return
            
            try:
                with open(annotated_image_path_after_action, 'rb') as img_file:
                    image_data_after_action = base64.b64encode(img_file.read()).decode('utf-8')

                # Model for vision analysis: pixtral-12b-2409
                vision_model = "pixtral-12b-2409"
                analysis_result = st.session_state.mistral_client.analyze_state_vision(
                    image_data_after_action, current_task, st.session_state.todo_objective, model_name=vision_model
                )

                analysis_summary = analysis_result.get('summary', 'No analysis summary provided.')
                add_message("assistant", f"**Vision Model (Pixtral-12B-2409) Analysis:** {analysis_summary}", "info")
                st.session_state.execution_summary.append({"task": current_task, "vision_analysis": analysis_result})
                if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                    st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]

                # C. Decision Making
                detected_error = analysis_result.get("error")
                task_completed = analysis_result.get("task_completed", False)
                objective_completed = analysis_result.get("objective_completed", False)

                if detected_error and detected_error.lower() not in ["null", "none", ""]:
                    add_message("assistant", f"⚠️ Error detected by vision model: {detected_error}. Stopping for now.", "error")
                    # Future: Implement re-planning logic here.
                    st.session_state.orchestrator_active = False
                elif objective_completed:
                    add_message("assistant", "🎉 Objective completed successfully!", "success")
                    st.session_state.orchestrator_active = False
                elif task_completed:
                    add_message("assistant", f"✅ Task '{current_task}' marked as completed.", "success")
                    st.session_state.current_task_index += 1
                else:
                    add_message("assistant", f"ℹ️ Task '{current_task}' not yet fully completed or action was part of a multi-step task. Will re-evaluate or proceed.", "info")
                    # The loop will re-run with the same task_idx if not incremented,
                    # or move to the next if incremented. analyze_and_decide should handle sub-steps.
            
            except Exception as e:
                add_message("assistant", f"Error during state analysis phase: {str(e)}\n{traceback.format_exc()}", "error")
                st.session_state.orchestrator_active = False
                # Rerun is at the end of the current task cycle block

            # Calculate approximate size of messages content (sum of lengths of string content)
            approx_messages_content_size = 0
            if 'messages' in st.session_state and st.session_state.messages:
                for msg in st.session_state.messages:
                    if isinstance(msg.get('content'), str):
                        approx_messages_content_size += len(msg['content'])

            # log_debug_message(f"DEBUG_SIZE: Before task cycle rerun (task_idx {task_idx}): len(messages) = {len(st.session_state.get('messages', []))}, approx_messages_content_size = {approx_messages_content_size}") # REMOVED

            # Log length of execution_summary
            # log_debug_message(f"DEBUG_SIZE: Before task cycle rerun (task_idx {task_idx}): len(execution_summary) = {len(st.session_state.get('execution_summary', []))}") # REMOVED

            # log_debug_message(f"DEBUG_STATE: Just before st.rerun() after orchestrator task cycle (task_idx {task_idx}), 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
            st.rerun()

        else: # All tasks processed (task_idx >= len(tasks))
            add_message("assistant", "✅ All tasks from todo.md have been processed. Performing final verification.", "info")
            # Perform a final vision analysis
            final_annotated_image_path = take_screenshot_and_analyze()
            if final_annotated_image_path:
                try:
                    with open(final_annotated_image_path, 'rb') as img_file:
                        final_image_data = base64.b64encode(img_file.read()).decode('utf-8')

                    final_analysis = st.session_state.mistral_client.analyze_state_vision(
                        final_image_data, "Final objective verification", st.session_state.todo_objective, model_name="pixtral-12b-2409" # Use updated vision model here too
                    )
                    final_summary = final_analysis.get('summary', 'No final summary.')
                    add_message("assistant", f"Final Check Summary: {final_summary}", "info")
                    if final_analysis.get("objective_completed"):
                        add_message("assistant", "🎉 Final verification confirms objective completed!", "success")
                    else:
                        add_message("assistant", "⚠️ Final verification suggests the objective may not be fully met.", "error")
                except Exception as e:
                    add_message("assistant", f"Error during final verification: {str(e)}", "error")
            else:
                add_message("assistant", "Could not take screenshot for final verification.", "error")

            st.session_state.orchestrator_active = False
            # log_debug_message(f"DEBUG_STATE: Just before st.rerun() after all tasks processed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
            st.rerun()

    # Auto-continue legacy automation if active (and orchestrator is not) - This part can be removed if legacy is fully deprecated.
    # This part was removed in prior refactoring, so no st.rerun() here.

    # Debug Log Expander moved to setup_sidebar()

if __name__ == "__main__":
    main()
