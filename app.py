import streamlit as st
import os
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
from mistral_client import MistralClient
from ollama_client import OllamaClient
from element_detector import ElementDetector
import todo_manager # Added import
import traceback
import re # Added import
from e2b_desktop import Sandbox # Corrected import
import asyncio
from image_utils import gridify_image # Added import
# st.components.v1.iframe is available via streamlit import as st

# Ensure datetime is imported if not already (it's imported as `from datetime import datetime`)
# import datetime # This specific import form might be needed if using datetime.datetime directly without prior specific import

def take_e2b_screenshot_and_display():
    """
    Captures a screenshot from the E2B session, optionally grids it, 
    and displays it in the chat.
    Returns the path to the (potentially gridded) image, or original if gridding fails, 
    or None if initial capture fails.
    """
    if not st.session_state.get('e2b_session'):
        # add_message("assistant", "E2B session not available to take screenshot.", "error") # Removed
        # add_message("assistant", "Debug (take_e2b_screenshot): Session not active, returning None.", "info") # Removed
        return None

    try:
        e2b_screenshots_dir = "e2b_screenshots"
        os.makedirs(e2b_screenshots_dir, exist_ok=True)

        # Capture screenshot
        image_bytes = st.session_state.e2b_session.screenshot() # This is already bytes

        # Generate filename and save
        # Using current datetime import style
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d_%H%M%S_%f")
        screenshot_filename = f"e2b_screenshot_{timestamp}.png"
        screenshot_filepath = os.path.join(e2b_screenshots_dir, screenshot_filename)

        with open(screenshot_filepath, "wb") as f:
            f.write(image_bytes)
        
        # Now, try to grid the saved screenshot
        gridded_screenshot_filename = f"gridded_e2b_screenshot_{timestamp}.png"
        gridded_screenshot_filepath = os.path.join(e2b_screenshots_dir, gridded_screenshot_filename)

        gridded_image_path_or_none = gridify_image(
            screenshot_filepath, 
            gridded_screenshot_filepath, 
            rows=10, 
            cols=10
        )

        if gridded_image_path_or_none:
            # add_message("assistant", gridded_image_path_or_none, msg_type="image", caption="Gridded E2B Desktop Screenshot (10x10)") # Removed
            # add_message("assistant", f"Debug (take_e2b_screenshot): Gridding successful, returning gridded path: {gridded_image_path_or_none}", "info") # Removed
            return gridded_image_path_or_none
        else:
            # add_message("assistant", "Failed to create gridded screenshot. Displaying original.", "warning") # Removed
            # add_message("assistant", screenshot_filepath, msg_type="image", caption="E2B Desktop Screenshot (Original - Gridding Failed)") # Removed
            # add_message("assistant", f"Debug (take_e2b_screenshot): Gridding failed, returning original path: {screenshot_filepath}", "info") # Removed
            return screenshot_filepath # Return original if gridding failed

    except Exception as e:
        # error_msg = f"Failed to take or process E2B screenshot: {str(e)}" # Original error message
        # add_message("assistant", error_msg, "error") # Removed
        # add_message("assistant", "Debug (take_e2b_screenshot): Exception during capture/processing, returning None.", "info") # Removed
        print(f"Error in take_e2b_screenshot_and_display: {str(e)}") # Keep server-side log
        print(traceback.format_exc()) # Keep server-side log for more details
        return None

def execute_e2b_click(target, screen_width=1024, screen_height=768, rows=10, cols=10):
    """
    Executes a click in the E2B session at the specified target.
    Target can be a grid cell (e.g., "A1") or coordinates (e.g., "100,200").
    """
    if not st.session_state.get('e2b_session'):
        add_message("assistant", "E2B session not available for click.", "error")
        return False

    x, y = -1, -1 # Initialize coordinates

    try:
        if ',' in target:
            # Parse as coordinates
            x_str, y_str = target.split(',')
            x = int(x_str.strip())
            y = int(y_str.strip())
            if not (0 <= x < screen_width and 0 <= y < screen_height):
                add_message("assistant", f"Coordinates ({x},{y}) are out of screen bounds ({screen_width}x{screen_height}).", "error")
                return False
        else:
            # Parse as grid cell
            target = target.upper().strip()
            if not (len(target) >= 2 and target[0].isalpha() and target[1:].isdigit()):
                 add_message("assistant", f"Invalid grid cell format: '{target}'. Expected e.g., 'A1', 'C5'.", "error")
                 return False

            row_char = target[0]
            col_num_str = target[1:]
            
            row_index = ord(row_char) - ord('A')
            col_index = int(col_num_str) - 1

            if not (0 <= row_index < rows and 0 <= col_index < cols):
                add_message("assistant", f"Grid cell '{target}' (row {row_index}, col {col_index}) is out of bounds for {rows}x{cols} grid.", "error")
                return False

            cell_width = screen_width / cols
            cell_height = screen_height / rows
            x = int((col_index + 0.5) * cell_width)
            y = int((row_index + 0.5) * cell_height)

        # Execute click
        st.session_state.e2b_session.left_click(x=x, y=y)
        add_message("assistant", f"E2B: Clicked at ({x},{y}) (target: {target})", "action")
        return True

    except ValueError:
        add_message("assistant", f"Error parsing target '{target}'. Ensure coordinates are numeric or grid cell is valid.", "error")
        return False
    except Exception as e:
        add_message("assistant", f"Error during E2B click: {str(e)}", "error")
        # print(f"E2B Click Error: {traceback.format_exc()}")
        return False

def execute_e2b_type(text_to_type):
    """
    Types the given text in the E2B session.
    """
    if not st.session_state.get('e2b_session'):
        add_message("assistant", "E2B session not available for typing.", "error")
        return False

    try:
        st.session_state.e2b_session.write(text_to_type)
        add_message("assistant", f"E2B: Typed: '{text_to_type}'", "action")
        return True
    except Exception as e:
        add_message("assistant", f"Error during E2B type: {str(e)}", "error")
        # print(f"E2B Type Error: {traceback.format_exc()}")
        return False

def get_screenshot_info():
    """Calculates total count and size of screenshots in predefined directories."""
    screenshots_dir = "screenshots"  # For Selenium screenshots
    e2b_screenshots_dir = "e2b_screenshots" # For E2B screenshots
    all_dirs = [screenshots_dir, e2b_screenshots_dir]
    
    total_files = 0
    total_size_bytes = 0
    
    for directory in all_dirs:
        if os.path.exists(directory):
            try:
                for filename in os.listdir(directory):
                    # Consider only common image file extensions
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')): 
                        filepath = os.path.join(directory, filename)
                        if os.path.isfile(filepath): # Make sure it's a file
                            try:
                                total_files += 1
                                total_size_bytes += os.path.getsize(filepath)
                            except OSError: # Handle potential errors like file deleted during iteration
                                pass 
            except OSError: # Handle potential errors like directory not accessible
                pass
                        
    total_size_mb = total_size_bytes / (1024 * 1024)
    return {"count": total_files, "total_size_mb": round(total_size_mb, 2)} # Rounded for display

def delete_all_screenshots():
    """Deletes all files in predefined screenshot directories and returns a status message."""
    screenshots_dir = "screenshots"
    e2b_screenshots_dir = "e2b_screenshots"
    all_dirs = [screenshots_dir, e2b_screenshots_dir]
    
    deleted_files_count = 0
    total_freed_space_bytes = 0
    errors_occurred = False
    
    for directory in all_dirs:
        if os.path.exists(directory):
            try:
                for filename in os.listdir(directory):
                    filepath = os.path.join(directory, filename)
                    try:
                        if os.path.isfile(filepath): # Make sure it's a file
                            file_size = os.path.getsize(filepath)
                            os.remove(filepath)
                            deleted_files_count += 1
                            total_freed_space_bytes += file_size
                    except Exception as e:
                        # Using print for server-side log, Streamlit message will be generic
                        print(f"Error deleting file {filepath}: {e}") 
                        errors_occurred = True
            except OSError as e:
                print(f"Error listing directory {directory}: {e}")
                errors_occurred = True
                        
    total_freed_space_mb = total_freed_space_bytes / (1024 * 1024)
    
    if errors_occurred:
        return f"Attempted to delete screenshots. Some errors occurred. Freed approx. {total_freed_space_mb:.2f} MB from {deleted_files_count} files."
    elif deleted_files_count == 0:
        return "No screenshot files found to delete."
    else:
        return f"Successfully deleted {deleted_files_count} screenshot files, freeing {total_freed_space_mb:.2f} MB."

def initialize_session_state():
    """Initialize session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
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
    if 'e2b_desktop_enabled' not in st.session_state:
        st.session_state.e2b_desktop_enabled = False
    if 'e2b_session' not in st.session_state:
        st.session_state.e2b_session = None
    if 'e2b_url' not in st.session_state:
        st.session_state.e2b_url = None
    if 'e2b_api_key_input' not in st.session_state: # Initialize E2B API key input
        st.session_state.e2b_api_key_input = ""
    if 'e2b_should_be_running' not in st.session_state:
        st.session_state.e2b_should_be_running = False
    # Ollama related session state
    if 'ollama_client' not in st.session_state:
        st.session_state.ollama_client = None
    if 'selected_ai_provider' not in st.session_state:
        st.session_state.selected_ai_provider = "Mistral" # Default to Mistral
    if 'ollama_model_input' not in st.session_state:
        st.session_state.ollama_model_input = "llama2" # Default model
    if 'ollama_host_input' not in st.session_state:
        st.session_state.ollama_host_input = "http://localhost:11434" # Default host
    if 'ollama_connection_status' not in st.session_state:
        st.session_state.ollama_connection_status = "Not Connected"

def setup_sidebar():
    """Setup sidebar for API key configuration and controls"""
    st.sidebar.title("🔧 Configuration")

    # AI Provider Selection
    st.sidebar.subheader("🤖 AI Provider")
    st.session_state.selected_ai_provider = st.sidebar.selectbox(
        "Choose AI Provider",
        ["Mistral", "Ollama"],
        index=["Mistral", "Ollama"].index(st.session_state.selected_ai_provider)
    )
    st.sidebar.divider()

    if st.session_state.selected_ai_provider == "Mistral":
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

    elif st.session_state.selected_ai_provider == "Ollama":
        st.sidebar.subheader("Ollama Configuration")
        st.session_state.ollama_model_input = st.sidebar.text_input(
            "Ollama Model",
            value=st.session_state.ollama_model_input,
            help="Specify the Ollama model to use (e.g., llama2, codellama)."
        )
        st.session_state.ollama_host_input = st.sidebar.text_input(
            "Ollama Host URL",
            value=st.session_state.ollama_host_input,
            help="Specify the URL of your Ollama server (e.g., http://localhost:11434)."
        )
        if st.sidebar.button("Connect to Ollama"):
            if not st.session_state.ollama_host_input or not st.session_state.ollama_model_input:
                st.sidebar.error("Please provide both Ollama model and host URL.")
                st.session_state.ollama_client = None
                st.session_state.ollama_connection_status = "Error: Missing details"
            else:
                try:
                    client = OllamaClient(
                        model=st.session_state.ollama_model_input,
                        host=st.session_state.ollama_host_input
                    )
                    if client.test_connection():
                        st.session_state.ollama_client = client
                        st.session_state.ollama_connection_status = f"✅ Connected to {st.session_state.ollama_model_input}"
                        st.sidebar.success(st.session_state.ollama_connection_status)
                    else:
                        st.session_state.ollama_client = None
                        st.session_state.ollama_connection_status = f"❌ Failed to connect to {st.session_state.ollama_host_input}"
                        st.sidebar.error(st.session_state.ollama_connection_status)
                except Exception as e:
                    st.session_state.ollama_client = None
                    st.session_state.ollama_connection_status = f"❌ Error: {str(e)}"
                    st.sidebar.error(st.session_state.ollama_connection_status)
        # Display current Ollama connection status
        st.sidebar.write(f"Ollama Status: {st.session_state.ollama_connection_status}")

    st.sidebar.divider()

    # E2B Desktop Configuration
    st.sidebar.subheader("☁️ E2B Desktop Configuration")
    st.session_state.e2b_api_key_input = st.sidebar.text_input(
        "E2B API Key",
        type="password",
        value=st.session_state.e2b_api_key_input,
        help="Enter your E2B API key. This will override the E2B_API_KEY environment variable if set."
    )

    if st.session_state.e2b_api_key_input:
        st.sidebar.success("✅ E2B API Key configured from UI.")
    elif os.getenv("E2B_API_KEY"):
        st.sidebar.info("ℹ️ E2B API Key configured from environment variable.")
    else: # This is the case where neither is set.
        st.sidebar.warning("⚠️ E2B API Key not set. Please enter it or set E2B_API_KEY env var.")
    
    st.session_state.e2b_desktop_enabled = st.sidebar.toggle(
        "Enable E2B Desktop Mode", 
        value=st.session_state.e2b_desktop_enabled,
        help="Toggle between Browser mode and E2B Desktop mode."
    )

    st.sidebar.divider()

    # Unified Session Controls
    st.sidebar.subheader("Session Controls")

    if not st.session_state.e2b_desktop_enabled: # Browser Mode Controls
        if st.sidebar.button("🚀 Start Browser", disabled=st.session_state.get('automation_active', False)):
            try:
                st.session_state.browser = BrowserAutomation()
                st.session_state.browser.start_browser()
                st.session_state.automation_active = True # Explicitly set
                st.sidebar.success("✅ Browser started")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"❌ Failed to start browser: {str(e)}")
        
        if st.sidebar.button("🛑 Stop Browser", disabled=not st.session_state.get('automation_active', False)):
            try:
                if st.session_state.browser:
                    st.session_state.browser.close()
                    st.session_state.browser = None
                st.session_state.automation_active = False # Explicitly set
                st.sidebar.success("✅ Browser stopped")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"❌ Failed to stop browser: {str(e)}")
    else: # E2B Desktop Mode Controls
        if st.sidebar.button("🚀 Start E2B Desktop", disabled=st.session_state.get('e2b_should_be_running', False)):
            st.session_state.e2b_should_be_running = True
            st.sidebar.info("E2B Desktop start initiated...") # User feedback
            st.rerun()

        if st.sidebar.button("🛑 Stop E2B Desktop", disabled=not st.session_state.get('e2b_should_be_running', False)):
            st.session_state.e2b_should_be_running = False
            st.sidebar.info("E2B Desktop stop initiated...") # User feedback
            st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("🖼️ Screenshot Management")
    info = get_screenshot_info() 
    st.sidebar.write(f"On-disk screenshots: {info['count']}")
    st.sidebar.write(f"Total size: {info['total_size_mb']:.2f} MB")

    if st.sidebar.button("🗑️ Clear All Screenshots"):
        status_message = delete_all_screenshots()
        if "error" in status_message.lower() or "failed" in status_message.lower():
            st.sidebar.error(status_message)
        elif "no screenshot files found" in status_message.lower():
            st.sidebar.warning(status_message)
        else:
            st.sidebar.success(status_message)
        st.rerun()
            
    # Status indicators
    st.sidebar.divider()
    st.sidebar.subheader("Status")

    # Display current mode
    current_mode = "E2B Desktop" if st.session_state.e2b_desktop_enabled else "Browser"
    st.sidebar.write(f"Active Mode: {current_mode}")

    # Display status for the active mode
    if not st.session_state.e2b_desktop_enabled: # Browser Mode
        browser_status_text = "🟢 Running" if st.session_state.get('automation_active', False) else "🔴 Stopped"
        st.sidebar.write(f"Browser Session: {browser_status_text}")
    else: # E2B Desktop Mode
        if st.session_state.get('e2b_should_be_running') and st.session_state.get('e2b_session'):
            e2b_status_text = "🟢 Running"
        elif st.session_state.get('e2b_should_be_running') and not st.session_state.get('e2b_session'):
            # This means it's set to run, but session not established yet by main()
            e2b_status_text = "⏳ Starting..." 
        else: 
            e2b_status_text = "🔴 Stopped"
        st.sidebar.write(f"E2B Session: {e2b_status_text}")

    # Keep Mistral AI Status (conditional)
    if st.session_state.selected_ai_provider == "Mistral":
        api_status = "🟢 Connected" if st.session_state.get('mistral_client') else "🔴 Not configured"
        st.sidebar.write(f"Mistral AI: {api_status}")
    elif st.session_state.selected_ai_provider == "Ollama":
        # Display simpler status for Ollama based on connection_status
        ollama_short_status = st.session_state.ollama_connection_status.split(' ')[0] # Gets "✅", "❌", "Not"
        if ollama_short_status == "✅":
             ollama_display_status = f"🟢 {st.session_state.ollama_connection_status}"
        elif ollama_short_status == "❌":
            ollama_display_status = f"🔴 {st.session_state.ollama_connection_status}"
        else: # Not Connected or other statuses
            ollama_display_status = f"⚪ {st.session_state.ollama_connection_status}"
        st.sidebar.write(f"Ollama: {ollama_display_status}")

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

def take_screenshot_and_analyze():
    """Take screenshot and analyze with element detection"""
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

def execute_browser_action(action_str: str) -> bool:
    """
    Executes a browser action string (e.g., click, type, press_key).
    Returns True if the action was attempted, False on format error or immediate failure.
    """
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
            # This action type signals overall completion, handled by orchestrator's decision logic.
            # For execute_browser_action, it means no direct browser op, but action is "valid".
            add_message("assistant", "Completion signal received.", "action")
            return True
        
        else:
            add_message("assistant", f"Unknown or malformed action: {action_str}", "error")
            return False
        
    except Exception as e:
        # This will catch errors from browser interaction (e.g., element not found) or format issues
        error_msg = f"Error executing action '{action_str}': {str(e)}"
        add_message("assistant", error_msg, "error")
        return False

# Note: The old execute_automation_step is removed as its logic is refactored or moved.

def main():
    """Main application function"""
    st.set_page_config(
        page_title="Web Automation Assistant",
        page_icon="🤖",
        layout="wide"
    )
    
    st.title("🤖 Web Automation Assistant")
    st.subheader("Powered by Mistral AI & Computer Vision")
    
    initialize_session_state()
    setup_sidebar()

    # E2B Desktop Management based on e2b_should_be_running
    # Start E2B session if in E2B mode, should be running, and no session exists
    if st.session_state.e2b_desktop_enabled and \
       st.session_state.e2b_should_be_running and \
       st.session_state.e2b_session is None:
        add_message("assistant", "Starting E2B Desktop session as per request...", "info")
        try:
            # Forcing synchronous execution if e2b.Sandbox() is async
            # This might block Streamlit's main thread, consider true async handling if performance issues arise.
            # However, for now, let's assume it can be called like this or it's a fast async op.
            # If e2b.Desktop() is strictly async and must be awaited:
            # st.session_state.e2b_session = asyncio.run(Desktop()) # This might not work in Streamlit context
            # Or use a thread:
            # with st.spinner("Starting E2B Desktop..."):
            #   loop = asyncio.new_event_loop()
            #   asyncio.set_event_loop(loop)
            #   st.session_state.e2b_session = loop.run_until_complete(Sandbox(api_key=st.session_state.e2b_api_key_input if st.session_state.e2b_api_key_input else os.getenv("E2B_API_KEY")))
            # For now, direct call as per initial plan assuming it's either sync or handles its own loop:
            if st.session_state.e2b_api_key_input:
                st.session_state.e2b_session = Sandbox(api_key=st.session_state.e2b_api_key_input)
                add_message("assistant", "Initializing E2B Sandbox with API key from UI.", "info")
            elif os.getenv("E2B_API_KEY"): # Check if env var is available as a fallback before calling Sandbox() without key
                st.session_state.e2b_session = Sandbox() # SDK will pick up env var
                add_message("assistant", "Initializing E2B Sandbox with API key from environment variable.", "info")
            else:
                # This case should ideally be prevented by the UI checks, but as a safeguard:
                st.session_state.e2b_session = Sandbox() 
                add_message("assistant", "Attempting to initialize E2B Sandbox without explicit API key (might use system default or fail).", "info")

            st.session_state.e2b_session.stream.start() # Start streaming
            st.session_state.e2b_url = st.session_state.e2b_session.stream.get_url() # Get stream URL
            add_message("assistant", f"E2B Desktop stream started. URL: {st.session_state.e2b_url}", "success")
            # Force a rerun to update the UI with the iframe and messages
            st.rerun()
        except Exception as e:
            add_message("assistant", f"Error starting E2B Desktop: {str(e)}", "error")
            st.session_state.e2b_session = None # Ensure session is None on error
            st.session_state.e2b_url = None
            st.session_state.e2b_should_be_running = False # Reset the trigger
            # Force a rerun to update the UI (e.g., hide iframe, update toggle, update status)
            st.rerun()

    # Stop E2B session if in E2B mode, should NOT be running, and a session exists
    elif st.session_state.e2b_desktop_enabled and \
         not st.session_state.e2b_should_be_running and \
         st.session_state.e2b_session is not None:
        add_message("assistant", "Stopping E2B Desktop session as per request...", "info")
        try:
            if hasattr(st.session_state.e2b_session, 'stream') and st.session_state.e2b_session.stream:
                st.session_state.e2b_session.stream.stop() # Stop streaming
            
            print(f"Attempting to close E2B session. Object type: {type(st.session_state.e2b_session)}")
            st.session_state.e2b_session.kill() # Using kill() method as confirmed by documentation
            add_message("assistant", "E2B Desktop session killed.", "success")
        except Exception as e:
            add_message("assistant", f"Error killing E2B Desktop session: {str(e)}", "error")
        finally:
            st.session_state.e2b_session = None
            st.session_state.e2b_url = None
            # Force a rerun to update the UI (e.g., hide iframe)
            st.rerun()

    # Display E2B Desktop if session is active and in E2B mode
    if st.session_state.e2b_desktop_enabled and \
       st.session_state.e2b_session and \
       st.session_state.e2b_url:
        st.components.v1.iframe(st.session_state.e2b_url, height=600)
    # The sidebar status messages are now handled in setup_sidebar()

    # E2B Automation Loop
    if st.session_state.get('e2b_automation_active'):
        if not st.session_state.get('e2b_desktop_enabled') or not st.session_state.get('e2b_session'):
            add_message("assistant", "E2B Desktop is no longer active. Stopping E2B automation.", "error")
            st.session_state.e2b_automation_active = False
            st.rerun()
            # return # Exit if E2B session was lost - st.rerun() handles the exit from this path.

        else: # E2B Automation step
            add_message("assistant", "E2B Automation: Taking screenshot...", "info")
            gridded_screenshot_path = take_e2b_screenshot_and_display()
            st.sidebar.info(f"DBG_RETURN_PATH: '{gridded_screenshot_path}'")

            if not gridded_screenshot_path:
                add_message("assistant", "E2B Automation: Failed to get screenshot. Cannot proceed.", "error")
                st.session_state.e2b_automation_active = False
                st.rerun()
            else:
                e2b_system_prompt = """
You are an expert AI assistant tasked with automating a remote desktop environment based on user objectives. You will be provided with a user's objective and a gridded screenshot of the current desktop state (or a textual description if vision is not available). The screenshot is overlaid with a 10x10 grid (labeled A1-A10, B1-B10, ..., J1-J10 where letters are rows A-J and numbers are columns 1-10). Your goal is to determine the single next best action to perform on the desktop to achieve the objective.

Based on the visual information from the gridded screenshot (or textual description) and the overall objective, you must output ONE of the following actions in the specified format:
1. CLICK(CELL_LABEL_OR_DESCRIPTOR) - e.g., CLICK(D5) or CLICK(the 'Submit' button)
2. TYPE(TEXT_TO_TYPE) - e.g., TYPE(Hello, world!) or TYPE(user@example.com, into=the username field)
3. SCROLL(DIRECTION) - DIRECTION must be UP, DOWN, LEFT, or RIGHT. e.g., SCROLL(DOWN)
4. COMPLETE(SUMMARY_OF_COMPLETION) - e.g., COMPLETE(Objective achieved.)
5. ERROR(REASON_FOR_ERROR) - e.g., ERROR(Cannot find button.)

Current Objective: {objective}
Previous Action (if any): {previous_action}
Analyze the provided gridded screenshot/description and output your next action.
""".format(objective=st.session_state.current_objective, previous_action=st.session_state.e2b_last_action or "None")
                add_message("assistant", "E2B Automation: Thinking...", "info")
                ai_response_text = ""

                try:
                    if st.session_state.selected_ai_provider == "Mistral":
                        if not st.session_state.mistral_client:
                            add_message("assistant", "Mistral client not available for E2B automation.", "error")
                            st.session_state.e2b_automation_active = False
                            st.rerun()
                            return # Added return

                        image_data_for_ai = None
                        with open(gridded_screenshot_path, 'rb') as img_file:
                            image_data_for_ai = base64.b64encode(img_file.read()).decode('utf-8')

                        multimodal_prompt = f"Objective: {st.session_state.current_objective}\nPrevious Action: {st.session_state.e2b_last_action or 'None'}\nAnalyze the screenshot and follow system instructions."
                        response_payload = st.session_state.mistral_client.analyze_and_decide(
                            image_b64=image_data_for_ai,
                            user_prompt=multimodal_prompt,
                            model_name="pixtral-large-latest",
                            current_context=e2b_system_prompt
                        )
                        ai_response_text = response_payload.get("action", "").strip() if isinstance(response_payload, dict) else str(response_payload).strip()

                    elif st.session_state.selected_ai_provider == "Ollama":
                        if not st.session_state.ollama_client:
                            add_message("assistant", "Ollama client not available for E2B automation.", "error")
                            st.session_state.e2b_automation_active = False
                            st.rerun()
                            return # Added return

                        # For Ollama, we'll provide a textual description of the gridded screenshot context
                        # A more advanced implementation might try to OCR the screenshot or describe it in more detail.
                        # For now, a generic message indicating a gridded view is available.
                        e2b_screen_description_for_ollama = f"Current gridded view of the E2B desktop is available (cells A1-J10). Previous action: {st.session_state.e2b_last_action or 'None'}. User objective: {st.session_state.current_objective}. Refer to system context for action format."

                        response_payload_ollama = st.session_state.ollama_client.analyze_and_decide(
                            user_objective=f"Given the E2B desktop state (gridded view), and the overall objective '{st.session_state.current_objective}', determine the next action.",
                            current_context=e2b_system_prompt, # Ollama's system prompt is inside the client method
                            screen_description=e2b_screen_description_for_ollama
                        )
                        ai_response_text = response_payload_ollama.get("action", "").strip() if isinstance(response_payload_ollama, dict) else str(response_payload_ollama).strip()

                    else:
                        add_message("assistant", "No AI provider selected for E2B automation.", "error")
                        st.session_state.e2b_automation_active = False
                        st.rerun()
                        return # Added return

                    if not ai_response_text:
                        add_message("assistant", "E2B Automation: AI did not return an action.", "error")
                        st.session_state.e2b_automation_active = False
                    else:
                        add_message("assistant", f"E2B AI Action: {ai_response_text}", "info") # This one was already there
                            st.session_state.e2b_last_action = ai_response_text

                            action_executed = False
                            if ai_response_text.upper().startswith("CLICK("):
                                target = ai_response_text[len("CLICK("):-1]
                                # Removed: add_message("assistant", f"Debug: Attempting to execute parsed action: CLICK on {target}", "info")
                                action_executed = execute_e2b_click(target, screen_width=1024, screen_height=768, rows=st.session_state.e2b_grid_rows, cols=st.session_state.e2b_grid_cols)
                            elif ai_response_text.upper().startswith("TYPE("):
                                text_to_type = ai_response_text[len("TYPE("):-1]
                                # Removed: add_message("assistant", f"Debug: Attempting to execute parsed action: TYPE '{text_to_type}'", "info")
                                action_executed = execute_e2b_type(text_to_type)
                            elif ai_response_text.upper().startswith("SCROLL("):
                                direction = ai_response_text[len("SCROLL("):-1].lower()
                                # Removed: add_message("assistant", f"Debug: Attempting to execute parsed action: SCROLL {direction}", "info")
                                add_message("assistant", f"E2B: SCROLL({direction}) requested (not yet implemented).", "action")
                                action_executed = True 
                            elif ai_response_text.upper().startswith("COMPLETE("):
                                summary = ai_response_text[len("COMPLETE("):-1]
                                add_message("assistant", f"E2B Automation: Objective COMPLETE: {summary}", "success")
                                st.session_state.e2b_automation_active = False
                                action_executed = True
                            elif ai_response_text.upper().startswith("ERROR("):
                                error_reason = ai_response_text[len("ERROR("):-1]
                                add_message("assistant", f"E2B Automation: AI reported an ERROR: {error_reason}", "error")
                                st.session_state.e2b_automation_active = False
                                action_executed = True 
                            else:
                                add_message("assistant", f"E2B Automation: Unknown AI action: {ai_response_text}", "error")
                                st.session_state.e2b_automation_active = False

                            if not action_executed and st.session_state.e2b_automation_active: 
                                 add_message("assistant", "E2B Automation: Action failed to execute. Stopping.", "error")
                                 st.session_state.e2b_automation_active = False

                except Exception as e:
                    add_message("assistant", f"E2B Automation: Error during AI interaction or action execution: {str(e)}", "error")
                    # print(traceback.format_exc()) 
                    st.session_state.e2b_automation_active = False

                if st.session_state.e2b_automation_active: 
                    time.sleep(1) 
                st.rerun() # Rerun to continue loop or reflect ended state.

    # Main chat interface
    st.write("Enter your automation objective and I'll help you navigate the web!")
    
    # Display chat history
    display_chat_history()
    
    # User input
    user_input = st.chat_input("What would you like me to do on the web?")
    
    if user_input:
        add_message("user", user_input)

        # If E2B Desktop is active and running, take a screenshot and then stop further processing for now.
        if st.session_state.get('e2b_desktop_enabled') and st.session_state.get('e2b_session'):
            add_message("assistant", "E2B mode: Capturing current desktop state...", "info")
            e2b_screenshot_path = take_e2b_screenshot_and_display()
            if e2b_screenshot_path:
                add_message("assistant", f"E2B Screenshot taken: {e2b_screenshot_path}", "info")
                # Placeholder for next steps (AI processing, etc.)
            else:
                add_message("assistant", "Could not capture E2B screenshot.", "error")
            
            st.session_state.current_objective = user_input # Still capture objective
            # Prevent falling into Selenium orchestrator logic for now
            st.rerun() 
            return 

        # Check prerequisites (only if not in active E2B mode, due to the early return above)
        if not st.session_state.mistral_client:
            add_message("assistant", "Please configure your Mistral AI API key in the sidebar first.", "error")
            st.rerun()
            return 
        
        # Prerequisites check
        if st.session_state.selected_ai_provider == "Mistral" and not st.session_state.get('mistral_client'):
            add_message("assistant", "Please configure your Mistral AI API key in the sidebar first.", "error")
            st.rerun()
            return
        elif st.session_state.selected_ai_provider == "Ollama" and not st.session_state.get('ollama_client'):
            add_message("assistant", "Please connect to your Ollama client in the sidebar first.", "error")
            st.rerun()
            return

        if not st.session_state.get('automation_active'): # Check if browser automation is active
            add_message("assistant", "Browser session is not running. Please start it using 'Start Browser' in Session Controls if you want to automate web tasks.", "info")
            st.rerun()
            return

        st.session_state.current_objective = user_input
        st.session_state.orchestrator_active = True
        st.session_state.automation_active = False
        st.session_state.current_task_index = 0
        st.session_state.execution_summary = []

        add_message("assistant", f"Received new objective: {user_input}. Initializing orchestrator and planning steps...")
        
        todo_manager.reset_todo_file(user_input)
        add_message("assistant", f"📝 `todo.md` reset for objective: {user_input}", "info")

        # Generate Steps
        generated_steps = []
        try:
            add_message("assistant", f"🧠 Generating steps using {st.session_state.selected_ai_provider}...", "info")
            if st.session_state.selected_ai_provider == "Mistral":
                if not st.session_state.mistral_client: # Should be caught by prerequisite check, but defensive
                    add_message("assistant", "Mistral client not initialized. Cannot generate steps.", "error")
                    st.session_state.orchestrator_active = False
                    st.rerun()
                    return
                generated_steps = st.session_state.mistral_client.generate_steps_for_todo(
                    user_prompt=user_input,
                    model_name="pixtral-large-latest" # Consider making model configurable
                )
            elif st.session_state.selected_ai_provider == "Ollama":
                if not st.session_state.ollama_client: # Should be caught by prerequisite check
                    add_message("assistant", "Ollama client not connected. Please connect in the sidebar.", "error")
                    st.session_state.orchestrator_active = False
                    st.rerun()
                    return
                generated_steps = st.session_state.ollama_client.generate_steps_for_todo(
                    user_prompt=user_input
                    # model_name can be specified here if needed, defaults to client's model
                )
            else:
                add_message("assistant", "No AI provider selected or configured for step generation.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return

            if not generated_steps:
                add_message("assistant", f"⚠️ Failed to generate steps or no steps were returned using {st.session_state.selected_ai_provider}. Please try rephrasing your objective.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return

            add_message("assistant", f"✅ Steps generated: {len(generated_steps)} steps.", "success")

            # Populate todo.md
            todo_manager.create_todo_file(user_input, generated_steps)
            add_message("assistant", "💾 `todo.md` populated with generated steps.", "info")

            # Update Session State from todo.md
            retrieved_todo = todo_manager.read_todo_file()
            st.session_state.todo_objective = retrieved_todo.get("objective")
            st.session_state.todo_tasks = retrieved_todo.get("tasks", [])
            st.session_state.current_task_index = 0 # Start from the first task

            # Display To-Do List
            plan_display_intro = "**Planning Agent (Pixtral-Large-Latest) says:** Planning complete. Here's the initial plan:"
            plan_display = f"{plan_display_intro}\n\n**Objective:** {st.session_state.todo_objective}\n\n"
            plan_display += "**Tasks:**\n"
            if st.session_state.todo_tasks:
                for i, task_item in enumerate(st.session_state.todo_tasks):
                    plan_display += f"- [ ] {task_item} \n"
            else:
                plan_display += "- No tasks defined yet."
            add_message("assistant", plan_display, "plan")

        except Exception as e:
            error_msg = f"Error during planning phase: {str(e)}\n{traceback.format_exc()}"
            add_message("assistant", error_msg, "error")
            st.session_state.orchestrator_active = False

        st.rerun()
    
    # Orchestrator Main Execution Loop
    if st.session_state.get('orchestrator_active') and st.session_state.todo_tasks:
        if not st.session_state.browser or not st.session_state.mistral_client:
            add_message("assistant", "Browser or Mistral client not initialized. Orchestrator cannot proceed.", "error")
            st.session_state.orchestrator_active = False
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
                st.rerun()
                return

            try:
                with open(annotated_image_path, 'rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')

                # Model for determining browser actions: mistral-small-latest
                action_decision_model = "mistral-small-latest"
                # For current_objective, pass the overall objective to give context to analyze_and_decide
                response = st.session_state.mistral_client.analyze_and_decide(
                    image_data, current_task, model_name=action_decision_model_mistral, current_context=st.session_state.todo_objective
                )
            elif st.session_state.selected_ai_provider == "Ollama":
                if not st.session_state.ollama_client:
                    add_message("assistant", "Ollama client not available for action decision.", "error")
                    st.session_state.orchestrator_active = False
                    st.rerun()
                    return

                # For Ollama, since it can't "see" the image, we describe the situation.
                # We pass the current task as the primary "user_objective" for this specific decision.
                # The overall objective is passed as "current_context".
                # The screen_description needs to be crafted. Since we just took a screenshot (annotated_image_path),
                # we can state that visual info was captured but the model needs to rely on text.
                # A more advanced version could try to extract text from the screenshot or elements if available.
                screen_description_for_ollama = f"A screenshot has been taken and annotated with element indices. The current task is '{current_task}'. The overall objective is '{st.session_state.todo_objective}'. Based on this task and the objective, decide the next browser action. If the task implies visual confirmation (e.g., 'Verify X is visible'), and you cannot confirm from text, you might need to state that or suggest a different type of step if the action language allows."
                if not annotated_image_path: # Fallback if screenshot failed
                    screen_description_for_ollama = "No visual information available (screenshot failed). Base decision on task and objective."

                response = st.session_state.ollama_client.analyze_and_decide(
                    user_objective=current_task, # Current task is the immediate objective for this decision
                    current_context=st.session_state.todo_objective, # Overall objective
                    screen_description=screen_description_for_ollama
                    # model_name can be specified here if desired for Ollama client
                )
            else:
                add_message("assistant", "No AI provider selected for action decision.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return

            thinking = response.get('thinking', 'No reasoning provided for action.')
            action_str = response.get('action', '')
            # Display reasoning based on provider
            provider_tag = "Mistral-Small-Latest" if st.session_state.selected_ai_provider == "Mistral" else st.session_state.ollama_client.model
            add_message("assistant", f"**Action Model ({provider_tag}) Reasoning:** {thinking}", "thinking")

            if not action_str:
                add_message("assistant", "No action could be determined. Trying task again or may need replan.", "error")
                st.session_state.execution_summary.append({"task": current_task, "action_model_response": response, "status": "No action determined"})
                st.rerun()
                return

            action_executed_successfully = execute_browser_action(action_str)
            st.session_state.execution_summary.append({"task": current_task, "action": action_str, "executed": action_executed_successfully})

            if not action_executed_successfully and action_str.lower() not in ['complete', 'done']:
                 add_message("assistant", f"Action '{action_str}' failed to execute properly. Will re-evaluate.", "error")

            except Exception as e:
                add_message("assistant", f"Error during action execution phase: {str(e)}\n{traceback.format_exc()}", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return

            # B. State Analysis (using pixtral-large-latest for analyze_state_vision)
            add_message("assistant", "🧐 Analyzing outcome of the action...", "info")
            time.sleep(1) # Brief pause for page to potentially update after action
            annotated_image_path_after_action = take_screenshot_and_analyze()

            if not annotated_image_path_after_action:
                add_message("assistant", "Failed to get screenshot for state analysis. Stopping.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return
            
            try:
                with open(annotated_image_path_after_action, 'rb') as img_file:
                    image_data_after_action = base64.b64encode(img_file.read()).decode('utf-8')

                # Model for vision analysis
                vision_model_mistral = "pixtral-12b-2409"
                analysis_result = {}

                if st.session_state.selected_ai_provider == "Mistral":
                    if not st.session_state.mistral_client:
                        add_message("assistant", "Mistral client not available for state analysis.", "error")
                        st.session_state.orchestrator_active = False
                        st.rerun()
                        return
                    analysis_result = st.session_state.mistral_client.analyze_state_vision(
                        image_data_after_action, current_task, st.session_state.todo_objective, model_name=vision_model_mistral
                    )
                elif st.session_state.selected_ai_provider == "Ollama":
                    if not st.session_state.ollama_client:
                        add_message("assistant", "Ollama client not available for state analysis.", "error")
                        st.session_state.orchestrator_active = False
                        st.rerun()
                        return

                    screen_description_for_ollama_vision = f"After an action, the current task is '{current_task}'. The overall objective is '{st.session_state.todo_objective}'. A new screen is available (screenshot taken) but cannot be visually processed by this model. Based on the task and objective, analyze the state (error, task_completed, objective_completed) and provide a summary."
                    if not annotated_image_path_after_action: # Fallback if screenshot failed
                         screen_description_for_ollama_vision = "No visual information available for state analysis (screenshot failed)."

                    analysis_result = st.session_state.ollama_client.analyze_state_vision(
                        current_task=current_task,
                        objective=st.session_state.todo_objective,
                        screen_description=screen_description_for_ollama_vision
                        # model_name can be specified here for Ollama client
                    )
                else:
                    add_message("assistant", "No AI provider selected for state analysis.", "error")
                    st.session_state.orchestrator_active = False
                    st.rerun()
                    return

                analysis_summary = analysis_result.get('summary', 'No analysis summary provided.')
                provider_tag_vision = vision_model_mistral if st.session_state.selected_ai_provider == "Mistral" else st.session_state.ollama_client.model
                add_message("assistant", f"**State Analysis Model ({provider_tag_vision}) Summary:** {analysis_summary}", "info")
                st.session_state.execution_summary.append({"task": current_task, "vision_analysis": analysis_result})

                # C. Decision Making
                detected_error = analysis_result.get("error") # Ensure this is consistently string or None
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

            st.rerun()

        else: # All tasks processed (task_idx >= len(tasks))
            add_message("assistant", "✅ All tasks from todo.md have been processed. Performing final verification.", "info")
            # Perform a final vision analysis
            final_annotated_image_path = take_screenshot_and_analyze()
            if final_annotated_image_path:
                try:
                    with open(final_annotated_image_path, 'rb') as img_file:
                        final_image_data = base64.b64encode(img_file.read()).decode('utf-8')

                    final_analysis = {}
                    if st.session_state.selected_ai_provider == "Mistral":
                        final_analysis = st.session_state.mistral_client.analyze_state_vision(
                            final_image_data, "Final objective verification", st.session_state.todo_objective, model_name="pixtral-12b-2409"
                        )
                    elif st.session_state.selected_ai_provider == "Ollama":
                        final_screen_desc = "Final verification: A screenshot is available. Assess if the overall objective appears complete based on this and the objective text."
                        if not final_annotated_image_path:
                            final_screen_desc = "Final verification: No screenshot available. Assess based on objective text only."
                        final_analysis = st.session_state.ollama_client.analyze_state_vision(
                            current_task="Final objective verification",
                            objective=st.session_state.todo_objective,
                            screen_description=final_screen_desc
                        )

                    final_summary = final_analysis.get('summary', 'No final summary.')
                    final_provider_tag = "Mistral" if st.session_state.selected_ai_provider == "Mistral" else st.session_state.ollama_client.model
                    add_message("assistant", f"Final Check Summary ({final_provider_tag}): {final_summary}", "info")

                    if final_analysis.get("objective_completed"): # Relies on boolean from analyze_state_vision
                        add_message("assistant", "🎉 Final verification confirms objective completed!", "success")
                    else:
                        add_message("assistant", "⚠️ Final verification suggests the objective may not be fully met.", "error")
                except Exception as e:
                    add_message("assistant", f"Error during final verification: {str(e)}", "error")
            else:
                add_message("assistant", "Could not take screenshot for final verification.", "error")

            st.session_state.orchestrator_active = False
            st.rerun()

    # Auto-continue legacy automation if active (and orchestrator is not) - This part can be removed if legacy is fully deprecated.
    if st.session_state.get('automation_active') and not st.session_state.get('orchestrator_active'):
        add_message("assistant", "Legacy automation loop triggered (should be deprecated).", "info")
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
