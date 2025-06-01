import streamlit as st
import os
# import shutil # Removed as it's no longer used
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
from e2b_automation import E2BDesktopAutomation # Added import
from mistral_client import MistralClient
from element_detector import ElementDetector
import todo_manager # Added import
import traceback
import re # Added import

# System Prompts
BROWSER_MODE_SYSTEM_PROMPT = """\
You are an AI assistant helping a user automate tasks on a web page.
You will be given screenshots of a web page with interactive elements (like buttons, links, input fields) annotated with numerical indices.
Your goal is to achieve the user's objective by performing a sequence of actions.
Available actions:
- navigate_to("URL"): Navigates to the given URL.
- click(index): Clicks the web element specified by its numerical index from the annotated screenshot.
- type("text_to_type", into="index_of_input_field"): Types the given text into the specified input field.
- press_key("key_name"): Simulates pressing a special key (e.g., 'Enter', 'Escape'). Common keys: enter, escape, tab.
- complete(): Use this action when the objective is fully achieved.
- done(): Use this action if you believe you are done with the current step or objective.
Analyze the screenshot and the user's objective carefully. Provide your reasoning (thinking process) and then the single next action to perform."""

E2B_MODE_SYSTEM_PROMPT = """\
You are an AI assistant helping a user automate tasks on a general desktop computer environment.
You will interact with this desktop by analyzing screenshots and deciding on actions to control the mouse and keyboard.
Indexed elements like in web pages are NOT available.
Your goal is to achieve the user's objective by performing a sequence of actions based on visual information from screenshots.
Available actions:
- navigate_to("URL"): Opens the Firefox browser (if available) and navigates to the given URL within the desktop environment.
- click_coordinates(x,y): Moves the mouse to the specified pixel coordinates (x,y) on the screen and performs a left click. You MUST determine these coordinates by visually analyzing the provided screenshot. For example, if a button is at pixel (100,250), use click_coordinates(100,250).
- type_text("text_to_type"): Types the given text at the current mouse cursor position or focused input field.
- press_key("key_name"): Simulates pressing a special keyboard key. Common PyAutoGUI key names include: 'enter', 'esc', 'tab', 'left', 'right', 'up', 'down', 'ctrl', 'alt', 'shift', 'f1' through 'f12', etc.
- complete(): Use this action when the overall objective is fully achieved.
- done(): Use this action if you believe you are done with the current step or objective.
Interaction Flow:
1. You will be given an objective and a screenshot of the desktop.
2. Analyze the screenshot to understand the current state.
3. If you need to click something, determine its (x,y) pixel coordinates from the screenshot. If you cannot determine the coordinates or are unsure, you can state what you are looking for or ask for clarification, but your primary goal is to issue an action.
4. Provide your reasoning (thinking process) and then the single next action to perform from the list above.
5. After your action, a new screenshot will usually be taken and presented to you."""

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
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'execution_mode' not in st.session_state:
        st.session_state.execution_mode = "Browser Use"
    if 'browser' not in st.session_state:
        st.session_state.browser = None
    if 'e2b_automation_instance' not in st.session_state:
        st.session_state.e2b_automation_instance = None
    if 'e2b_api_key' not in st.session_state: # Added for E2B API Key
        st.session_state.e2b_api_key = os.getenv("E2B_API_KEY", "")
    if 'mistral_client' not in st.session_state:
        st.session_state.mistral_client = None
    if 'element_detector' not in st.session_state:
        st.session_state.element_detector = ElementDetector()
    if 'automation_active' not in st.session_state:
        st.session_state.automation_active = False
    if 'current_objective' not in st.session_state:
        st.session_state.current_objective = None
    if 'step_count' not in st.session_state:
        st.session_state.step_count = 0
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

    st.sidebar.subheader("E2B API Key")
    e2b_api_key_input = st.sidebar.text_input(
        "E2B API Key",
        value=st.session_state.get("e2b_api_key", ""), # Get initial value from session state
        type="password",
        help="Enter your E2B API key. This will override the E2B_API_KEY environment variable if set."
    )

    if e2b_api_key_input:
        st.session_state.e2b_api_key = e2b_api_key_input
        # No direct validation here, but we can show it's set.
        # The actual validation happens when E2BDesktopAutomation tries to use it.
        st.sidebar.success("✅ E2B API Key provided via input field.")
    elif st.session_state.get("e2b_api_key"): # Check if it was pre-filled (e.g. from env var via initialize_session_state)
        st.sidebar.info("ℹ️ E2B API Key is pre-filled.")
    # else: # Removed the warning to avoid clutter if env var is primary method
        # st.sidebar.warning("⚠️ Please enter your E2B API key or set E2B_API_KEY environment variable.")
    st.sidebar.divider() # Add a divider after this section

    st.sidebar.subheader("Execution Mode")
    st.radio(
        label="Select Mode",
        options=("Browser Use", "E2B Desktop Computer Use"),
        key='execution_mode',
    )
    
    st.sidebar.subheader("Browser Controls")
    
    if st.sidebar.button("🚀 Start Browser", disabled=st.session_state.automation_active):
        if st.session_state.execution_mode == "Browser Use":
            try:
                st.session_state.browser = BrowserAutomation()
                st.session_state.browser.start_browser()
                st.session_state.automation_active = True
                st.sidebar.success("✅ Browser started for Browser Use")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to start browser: {str(e)}")
        elif st.session_state.execution_mode == "E2B Desktop Computer Use":
            try:
                # The API key from sidebar input is in st.session_state.e2b_api_key
                # E2BDesktopAutomation's constructor will use this, or fallback to env var, or raise error.
                key_from_sidebar_or_env = st.session_state.get("e2b_api_key", "") # This could be from input or prefilled env

                # We can add a preliminary check here for better UX before attempting instantiation
                if not key_from_sidebar_or_env and not os.getenv("E2B_API_KEY"): # Check if neither UI nor env var has it
                     st.sidebar.error("❌ E2B API Key is not set. Please enter it in the sidebar or set the E2B_API_KEY environment variable.")
                else:
                    # Pass the key from session state. If it's empty, E2BDesktopAutomation will try os.getenv.
                    st.session_state.e2b_automation_instance = E2BDesktopAutomation(api_key=key_from_sidebar_or_env)
                    st.session_state.e2b_automation_instance.start_session() # This might raise error if API key ultimately fails
                    st.session_state.automation_active = True
                    st.sidebar.success("✅ E2B Session started")
            except ValueError as ve: # Catch specific error from E2BDesktopAutomation if key is missing
                st.sidebar.error(f"❌ E2B Config Error: {str(ve)}")
            except Exception as e: # Catch other errors during session start
                st.sidebar.error(f"❌ Failed to start E2B session: {str(e)}")
    
    if st.sidebar.button("🛑 Stop Browser", disabled=not st.session_state.automation_active):
        if st.session_state.execution_mode == "Browser Use":
            try:
                if st.session_state.browser:
                    st.session_state.browser.close()
                    st.session_state.browser = None
                st.session_state.automation_active = False
                st.sidebar.success("✅ Browser stopped for Browser Use")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to stop browser: {str(e)}")
        elif st.session_state.execution_mode == "E2B Desktop Computer Use":
            try:
                if st.session_state.e2b_automation_instance:
                    st.session_state.e2b_automation_instance.close_session()
                    st.session_state.e2b_automation_instance = None
                st.session_state.automation_active = False
                st.sidebar.success("✅ E2B Session stopped")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to stop E2B session: {str(e)}")
    
    st.sidebar.divider()
    st.sidebar.subheader("Status")
    
    if st.session_state.execution_mode == "Browser Use":
        browser_status = "🟢 Running" if st.session_state.browser and st.session_state.automation_active else "🔴 Stopped"
        st.sidebar.write(f"Browser: {browser_status}")
    elif st.session_state.execution_mode == "E2B Desktop Computer Use":
        e2b_status = "🟢 Running" if st.session_state.e2b_automation_instance and st.session_state.e2b_automation_instance._is_session_active else "🔴 Stopped"
        st.sidebar.write(f"E2B Session: {e2b_status}")
    
    api_status = "🟢 Connected" if st.session_state.mistral_client else "🔴 Not configured"
    st.sidebar.write(f"Mistral AI: {api_status}")

    resolved_e2b_key = st.session_state.get("e2b_api_key") or os.getenv("E2B_API_KEY")
    e2b_api_status = "🟢 Configured" if resolved_e2b_key else "🔴 Not configured"
    st.sidebar.write(f"E2B API Key: {e2b_api_status}")

    st.sidebar.divider()
    current_file_count = get_current_screenshot_file_count()
    st.sidebar.caption(f"On-disk Screenshots: {current_file_count}")

    st.sidebar.divider()
    st.sidebar.subheader("Screenshot Management")
    if st.sidebar.button("⚠️ Delete All Screenshots Now"):
        clear_screenshots_directory_and_history()
        st.rerun()

def display_chat_history():
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
            elif message["type"] == "plan":
                st.markdown(message["content"])
            elif message["type"] == "info":
                st.info(f"ℹ️ {message['content']}")
            elif message["type"] == "success":
                st.success(f"✅ {message['content']}")

def add_message(role, content, msg_type="text", caption=None):
    message = {
        "role": role,
        "type": msg_type,
        "content": content,
        "timestamp": datetime.now()
    }
    if caption:
        message["caption"] = caption
    st.session_state.messages.append(message)
    if len(st.session_state.messages) > MAX_CHAT_MESSAGES:
        st.session_state.messages = st.session_state.messages[-MAX_CHAT_MESSAGES:]

def take_screenshot_and_analyze():
    if st.session_state.execution_mode == "Browser Use":
        try:
            if not st.session_state.browser:
                raise Exception("Browser not started")
            screenshot_path = st.session_state.browser.take_screenshot()
            add_message("assistant", screenshot_path, "image", "Current page screenshot")
            annotated_image_path = st.session_state.element_detector.detect_and_annotate_elements(screenshot_path, st.session_state.browser)
            add_message("assistant", annotated_image_path, "image", "Elements detected and indexed")
            return annotated_image_path
        except Exception as e:
            error_msg = f"Failed to take screenshot: {str(e)}"
            add_message("assistant", error_msg, "error")
            return None
    elif st.session_state.execution_mode == "E2B Desktop Computer Use":
        if st.session_state.e2b_automation_instance:
            add_message("assistant", "Attempting to take screenshot via E2B...", "info")
            local_e2b_screenshot_path = "e2b_screenshot.png"
            screenshot_path = st.session_state.e2b_automation_instance.take_screenshot(local_e2b_screenshot_path)
            if screenshot_path:
                add_message("assistant", screenshot_path, "image", "E2B Desktop Screenshot")
                annotated_image_path = st.session_state.element_detector.detect_and_annotate_elements(screenshot_path, None)
                if annotated_image_path != screenshot_path :
                        add_message("assistant", annotated_image_path, "image", "E2B Elements detected (if any)")
                else:
                    add_message("assistant", "Element detection on E2B screenshot may not be applicable or failed.", "info")
                return annotated_image_path if annotated_image_path else screenshot_path
            else:
                add_message("assistant", "Failed to take E2B screenshot.", "error")
                return None
        else:
            add_message("assistant", "E2B session not active. Cannot take screenshot.", "error")
            return None

def execute_browser_action(action_str: str) -> bool:
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
                    add_message("assistant", f"Clicked element at index {index}", "action")
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
                    url_to_navigate = url_with_quotes.strip("'\"")
                    if not url_to_navigate:
                        add_message("assistant", f"Could not extract URL from navigate_to action (after stripping): {action_str}", "error")
                        return False
                    if not (url_to_navigate.startswith("http://") or url_to_navigate.startswith("https://")):
                        add_message("assistant", f"Invalid URL format for navigation: {url_to_navigate}. Must start with http:// or https://", "error")
                        return False
                    add_message("assistant", f"Navigating to: {url_to_navigate}", "action")
                    try:
                        st.session_state.browser.navigate_to(url_to_navigate)
                        add_message("assistant", f"Successfully navigated to {url_to_navigate}", "success")
                        return True
                    except Exception as e_nav:
                        error_msg = f"Failed to navigate to {url_to_navigate}: {str(e_nav)}\n{traceback.format_exc()}"
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
            error_msg = f"Error executing action '{action_str}': {str(e)}\n{traceback.format_exc()}"
            add_message("assistant", error_msg, "error")
            return False
    elif st.session_state.execution_mode == "E2B Desktop Computer Use":
        if not st.session_state.e2b_automation_instance:
            add_message("assistant", "E2B session not active. Cannot execute action.", "error")
            return False
        action_str_lower = action_str.lower()
        try:
            if action_str_lower.startswith('navigate_to('):
                match = re.search(r"navigate_to\(([^)]+)\)", action_str, re.IGNORECASE)
                if match:
                    url_with_quotes = match.group(1)
                    url_to_navigate = url_with_quotes.strip("'\"")
                    if not (url_to_navigate.startswith("http://") or url_to_navigate.startswith("https://")):
                            add_message("assistant", f"Invalid URL format for navigation: {url_to_navigate}. Must start with http:// or https://", "error")
                            return False
                    add_message("assistant", f"E2B: Navigating to {url_to_navigate}", "action")
                    st.session_state.e2b_automation_instance.navigate_to(url_to_navigate)
                    return True
                else:
                    add_message("assistant", f"Invalid navigate_to action format for E2B: {action_str}", "error")
                    return False
            elif action_str_lower.startswith('click_coordinates('):
                match = re.search(r"click_coordinates\((\d+)\s*,\s*(\d+)\)", action_str_lower)
                if match:
                    x_coord = int(match.group(1))
                    y_coord = int(match.group(2))
                    add_message("assistant", f"E2B: Clicking at coordinates ({x_coord},{y_coord})", "action")
                    try:
                        st.session_state.e2b_automation_instance.click_at_coords(x_coord, y_coord) # type: ignore
                        return True
                    except Exception as e_click_coords:
                        error_msg = f"E2B: Error during click_coordinates({x_coord},{y_coord}): {str(e_click_coords)}"
                        add_message("assistant", error_msg, "error")
                        return False
                else:
                    add_message("assistant", f"E2B: Invalid click_coordinates format: {action_str}. Expected 'click_coordinates(x,y)'.", "error")
                    return False
            elif action_str_lower.startswith('click('):
                # This existing 'click(description_or_index)' handler
                add_message("assistant",
                            f"E2B: Action '{action_str}' is not a supported click format for E2B mode. "
                            "Please use 'click_coordinates(x,y)' after determining pixel coordinates from a screenshot. "
                            "Descriptive clicks like 'click(button name)' or indexed clicks 'click(1)' are not supported in E2B mode.",
                            "info")
                return False # Indicate action was not successfully parsed or executed
            elif action_str_lower.startswith('type('):
                match = re.search(r"type\(['\"](.*?)['\"](\s*,\s*into\s*=\s*['\"](.*?)['\"])?\)", action_str, re.IGNORECASE)
                if match:
                    text_to_type = match.group(1)
                    add_message("assistant", f"E2B: Typing text '{text_to_type}'. Target selector (if any) ignored.", "action")
                    st.session_state.e2b_automation_instance.type_text(text_to_type)
                    return True
                else:
                    add_message("assistant", f"Invalid type action format for E2B: {action_str}", "error")
                    return False
            elif action_str_lower.startswith('press_key('):
                match = re.search(r"press_key\(['\"](.*?)['\"]\)", action_str_lower)
                if match:
                    key_name = match.group(1).lower()
                    add_message("assistant", f"E2B: Pressing key '{key_name}'", "action")
                    st.session_state.e2b_automation_instance.press_key(key_name)
                    return True
                else:
                    add_message("assistant", f"Invalid press_key action format for E2B: {action_str}", "error")
                    return False
            elif 'complete' in action_str_lower or 'done' in action_str_lower:
                add_message("assistant", "E2B: Completion signal received.", "action")
                return True
            else:
                add_message("assistant", f"E2B: Unknown or malformed action: {action_str}", "error")
                return False
        except Exception as e:
            error_msg = f"E2B: Error executing action '{action_str}': {str(e)}\n{traceback.format_exc()}"
            add_message("assistant", error_msg, "error")
            return False

def main():
    st.set_page_config(
        page_title="Web Automation Assistant",
        page_icon="🤖",
        layout="wide"
    )
    st.title("Mistral Browser Use")
    st.subheader("Powered by Mistral AI & Computer Vision")
    
    initialize_session_state()
    setup_sidebar()
    
    st.write("Enter your automation objective and I'll help you navigate the web!")
    display_chat_history()
    
    user_input = st.chat_input("What would you like me to do on the web?", disabled=st.session_state.get('orchestrator_active', False))
    
    if user_input:
        add_message("user", user_input)
        
        if not st.session_state.mistral_client:
            add_message("assistant", "Please configure your Mistral AI API key in the sidebar first.", "error")
            st.rerun()
            return
        
        if st.session_state.execution_mode == "Browser Use":
            if not st.session_state.browser:
                add_message("assistant", "Please start the browser first using the sidebar controls (Browser Use mode).", "error")
                st.rerun()
                return
        elif st.session_state.execution_mode == "E2B Desktop Computer Use":
            if not st.session_state.e2b_automation_instance or not st.session_state.e2b_automation_instance._is_session_active:
                add_message("assistant", "Please start the E2B session first using the sidebar controls (E2B mode).", "error")
                st.rerun()
                return

        st.session_state.user_input_for_planning = user_input
        st.session_state.planning_requested = True
        st.session_state.orchestrator_active = False
        st.session_state.todo_tasks = []
        st.session_state.current_task_index = 0
        st.session_state.execution_summary = []
        st.rerun()

    if st.session_state.get('planning_requested'):
        st.session_state.planning_requested = False
        current_objective_for_planning = st.session_state.user_input_for_planning
        st.session_state.user_input_for_planning = None
        st.session_state.current_objective = current_objective_for_planning
        st.session_state.automation_active = False
        st.session_state.current_task_index = 0
        st.session_state.execution_summary = []
        add_message("assistant", f"Received new objective: {current_objective_for_planning}. Initializing orchestrator and planning steps...")
        todo_manager.reset_todo_file(current_objective_for_planning)
        add_message("assistant", f"📝 `todo.md` reset for objective: {current_objective_for_planning}", "info")
        try:
            if not st.session_state.mistral_client:
                add_message("assistant", "Mistral client not initialized. Cannot generate steps.", "error")
                st.rerun()
                return
            add_message("assistant", "🧠 Generating steps with pixtral-large-latest...", "info")
            selected_system_prompt = BROWSER_MODE_SYSTEM_PROMPT if st.session_state.execution_mode == "Browser Use" else E2B_MODE_SYSTEM_PROMPT
            generated_steps = st.session_state.mistral_client.generate_steps_for_todo( # type: ignore
                user_prompt=current_objective_for_planning,
                model_name="pixtral-large-latest",
                system_prompt_override=selected_system_prompt
            )
            if not generated_steps:
                add_message("assistant", "⚠️ Failed to generate steps or no steps were returned. Please try rephrasing your objective.", "error")
                st.rerun()
                return
            add_message("assistant", f"✅ Steps generated: {len(generated_steps)} steps.", "success")
            todo_manager.create_todo_file(current_objective_for_planning, generated_steps)
            add_message("assistant", "💾 `todo.md` populated with generated steps.", "info")
            retrieved_todo = todo_manager.read_todo_file()
            st.session_state.todo_objective = retrieved_todo.get("objective")
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
            st.session_state.orchestrator_active = True
        except Exception as e:
            error_msg = f"Error during planning phase: {str(e)}\n{traceback.format_exc()}"
            add_message("assistant", error_msg, "error")
            st.session_state.orchestrator_active = False
        st.rerun()

    if st.session_state.get('orchestrator_active') and st.session_state.todo_tasks:
        if not st.session_state.mistral_client:
            add_message("assistant", "Mistral client not initialized. Orchestrator cannot proceed.", "error")
            st.session_state.orchestrator_active = False
            st.rerun(); return
        if st.session_state.execution_mode == "Browser Use" and not st.session_state.browser:
            add_message("assistant", "Browser session not active. Orchestrator cannot proceed.", "error")
            st.session_state.orchestrator_active = False; st.rerun(); return
        elif st.session_state.execution_mode == "E2B Desktop Computer Use" and \
             (not st.session_state.e2b_automation_instance or not st.session_state.e2b_automation_instance._is_session_active):
            add_message("assistant", "E2B session not active. Orchestrator cannot proceed.", "error")
            st.session_state.orchestrator_active = False; st.rerun(); return

        task_idx = st.session_state.current_task_index
        tasks = st.session_state.todo_tasks
        if task_idx < len(tasks):
            current_task = tasks[task_idx]
            add_message("assistant", f"🚀 Executing Task {task_idx + 1}/{len(tasks)}: {current_task}", "info")
            add_message("assistant", "🤔 Thinking on how to execute the current task...", "thinking")
            annotated_image_path = take_screenshot_and_analyze()
            if not annotated_image_path:
                add_message("assistant", "Failed to get screenshot for action decision. Stopping.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return
            try:
                with open(annotated_image_path, 'rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')
                action_decision_model = "pixtral-large-2411"
                selected_system_prompt = BROWSER_MODE_SYSTEM_PROMPT if st.session_state.execution_mode == "Browser Use" else E2B_MODE_SYSTEM_PROMPT
                response = st.session_state.mistral_client.analyze_and_decide( # type: ignore
                    image_data,
                    current_task,
                    model_name=action_decision_model,
                    current_context=st.session_state.todo_objective,
                    system_prompt_override=selected_system_prompt
                )
                thinking = response.get('thinking', 'No reasoning provided for action.')
                action_str = response.get('action', '')

                # Check for structured errors from analyze_and_decide
                error_action_prefix = "ERROR_"
                if action_str.startswith(error_action_prefix):
                    add_message("assistant", f"**Action Model (Pixtral-Large-2411) Error:** {thinking}", "error") # Display thinking which now contains the error details
                    add_message("assistant", f"The AI model encountered an issue ({action_str}). Stopping current automation. Please review the error and consider trying again or modifying the objective.", "error")
                    st.session_state.execution_summary.append({"task": current_task, "action_model_response": response, "status": f"AI Error: {action_str}"})
                    if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                        st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]
                    st.session_state.orchestrator_active = False # Stop orchestrator
                    st.rerun()
                    return

                add_message("assistant", f"**Action Model (Pixtral-Large-2411) Reasoning:** {thinking}", "thinking")
                if not action_str: # This case might be less likely if errors are caught above, but good for safety.
                    add_message("assistant", "No action could be determined by the AI model. Stopping current automation.", "error")
                    st.session_state.execution_summary.append({"task": current_task, "action_model_response": response, "status": "No action determined"})
                    if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                        st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]
                    st.session_state.orchestrator_active = False # Stop orchestrator
                    st.rerun()
                    return

                action_executed_successfully = execute_browser_action(action_str)
                st.session_state.execution_summary.append({"task": current_task, "action": action_str, "executed": action_executed_successfully})
                if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                    st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]
                if not action_executed_successfully and action_str.lower() not in ['complete', 'done']:
                     add_message("assistant", f"Action '{action_str}' failed to execute properly. Will re-evaluate.", "error")
            except Exception as e:
                add_message("assistant", f"Error during action decision or execution phase: {str(e)}\n{traceback.format_exc()}", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return
            add_message("assistant", "🧐 Analyzing outcome of the action...", "info")
            time.sleep(1)
            annotated_image_path_after_action = take_screenshot_and_analyze()
            if not annotated_image_path_after_action:
                add_message("assistant", "Failed to get screenshot for state analysis. Stopping.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return
            try:
                with open(annotated_image_path_after_action, 'rb') as img_file:
                    image_data_after_action = base64.b64encode(img_file.read()).decode('utf-8')
                vision_model = "pixtral-12b-2409"
                analysis_result = st.session_state.mistral_client.analyze_state_vision(
                    image_data_after_action, current_task, st.session_state.todo_objective, model_name=vision_model
                )
                analysis_summary = analysis_result.get('summary', 'No analysis summary provided.')
                add_message("assistant", f"**Vision Model (Pixtral-12B-2409) Analysis:** {analysis_summary}", "info")
                st.session_state.execution_summary.append({"task": current_task, "vision_analysis": analysis_result})
                if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                    st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]
                detected_error = analysis_result.get("error")
                task_completed = analysis_result.get("task_completed", False)
                objective_completed = analysis_result.get("objective_completed", False)
                if detected_error and detected_error.lower() not in ["null", "none", ""]:
                    add_message("assistant", f"⚠️ Error detected by vision model: {detected_error}. Stopping for now.", "error")
                    st.session_state.orchestrator_active = False
                elif objective_completed:
                    add_message("assistant", "🎉 Objective completed successfully!", "success")
                    st.session_state.orchestrator_active = False
                elif task_completed:
                    add_message("assistant", f"✅ Task '{current_task}' marked as completed.", "success")
                    st.session_state.current_task_index += 1
                else:
                    add_message("assistant", f"ℹ️ Task '{current_task}' not yet fully completed or action was part of a multi-step task. Will re-evaluate or proceed.", "info")
            except Exception as e:
                add_message("assistant", f"Error during state analysis phase: {str(e)}\n{traceback.format_exc()}", "error")
                st.session_state.orchestrator_active = False
            st.rerun()
        else:
            add_message("assistant", "✅ All tasks from todo.md have been processed. Performing final verification.", "info")
            final_annotated_image_path = take_screenshot_and_analyze()
            if final_annotated_image_path:
                try:
                    with open(final_annotated_image_path, 'rb') as img_file:
                        final_image_data = base64.b64encode(img_file.read()).decode('utf-8')
                    final_analysis = st.session_state.mistral_client.analyze_state_vision(
                        final_image_data, "Final objective verification", st.session_state.todo_objective, model_name="pixtral-12b-2409"
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
            st.rerun()

if __name__ == "__main__":
    main()
