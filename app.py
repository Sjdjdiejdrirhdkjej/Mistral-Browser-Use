import streamlit as st
import os
# import shutil # Removed as it's no longer used
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
from mistral_client import MistralClient
from ollama_client import OllamaClient # Added import
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
    if 'browser' not in st.session_state:
        st.session_state.browser = None
    if 'mistral_client' not in st.session_state:
        st.session_state.mistral_client = None
    if 'ollama_client' not in st.session_state: # Added for Ollama
        st.session_state.ollama_client = None
    if 'ai_provider' not in st.session_state: # Added for AI provider selection
        st.session_state.ai_provider = "Mistral" # Default to Mistral
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

    # AI Provider Selection
    st.sidebar.subheader("AI Provider")
    ai_provider_choice = st.sidebar.selectbox(
        "Choose AI Provider",
        ("Mistral", "Ollama"),
        index=["Mistral", "Ollama"].index(st.session_state.ai_provider)
    )
    st.session_state.ai_provider = ai_provider_choice

    if st.session_state.ai_provider == "Mistral":
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
                st.sidebar.success("✅ Mistral API Key configured")
                st.session_state.ollama_client = None # Clear other client
        else:
            st.sidebar.warning("⚠️ Please enter your Mistral AI API key")
            st.session_state.mistral_client = None
    
    elif st.session_state.ai_provider == "Ollama":
        st.sidebar.subheader("Ollama Configuration")
        ollama_host = st.sidebar.text_input(
            "Ollama Host URL",
            value=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            help="Enter the URL of your Ollama instance (e.g., http://localhost:11434)"
        )
        if ollama_host:
            if st.session_state.ollama_client is None or st.session_state.ollama_client.client._client.host != ollama_host:
                st.session_state.ollama_client = OllamaClient(host=ollama_host)
                st.session_state.mistral_client = None # Clear other client

            # Check Ollama service reachability and model availability
            target_ollama_model = "llama3.2" # Define the target model
            if st.session_state.ollama_client:
                try:
                    # Try to list models to confirm connection
                    st.session_state.ollama_client.list_models()
                    st.sidebar.success(f"✅ Connected to Ollama at {ollama_host}")

                    # Check for specific model
                    if st.session_state.ollama_client.is_model_available(target_ollama_model):
                        st.sidebar.success(f"✅ Model '{target_ollama_model}' is available locally.")
                    else:
                        st.sidebar.warning(f"⚠️ Model '{target_ollama_model}' not found locally.")
                        if st.sidebar.button(f"📥 Download '{target_ollama_model}' Model"):
                            with st.spinner(f"Pulling '{target_ollama_model}'... This may take a while. See console for progress."):
                                success, message = st.session_state.ollama_client.pull_model(target_ollama_model)
                            if success:
                                st.sidebar.success(message)
                                # Rerun to update model status display
                                st.rerun()
                            else:
                                st.sidebar.error(message)
                except requests.exceptions.ConnectionError: # More specific error for connection
                    st.sidebar.error(f"❌ Failed to connect to Ollama at {ollama_host}. Ensure `ollama serve` is running.")
                    st.session_state.ollama_client = None
                except Exception as e: # Catch other potential errors from client methods
                    st.sidebar.error(f"❌ Error interacting with Ollama: {e}")
                    st.session_state.ollama_client = None
            # This else corresponds to `if ollama_host:`
        else:
            st.sidebar.warning("⚠️ Please enter the Ollama host URL.")
            st.session_state.ollama_client = None

    st.sidebar.divider()
    # Browser Controls
    st.sidebar.subheader("Browser Controls")
    
    if st.sidebar.button("🚀 Start Browser", disabled=st.session_state.automation_active):
        try:
            st.session_state.browser = BrowserAutomation()
            st.session_state.browser.start_browser()
            st.sidebar.success("✅ Browser started")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to start browser: {str(e)}")
    
    if st.sidebar.button("🛑 Stop Browser", disabled=not st.session_state.automation_active):
        try:
            if st.session_state.browser:
                st.session_state.browser.close()
                st.session_state.browser = None
                st.session_state.automation_active = False
            st.sidebar.success("✅ Browser stopped")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to stop browser: {str(e)}")
    
    # Status indicators
    st.sidebar.divider()
    st.sidebar.subheader("Status")
    
    browser_status = "🟢 Running" if st.session_state.browser and st.session_state.automation_active else "🔴 Stopped"
    st.sidebar.write(f"🌐 Browser: {browser_status}")

    st.sidebar.subheader("AI Provider Status")
    if st.session_state.ai_provider == "Mistral":
        if st.session_state.mistral_client:
            st.sidebar.write("🤖 Mistral AI: ✅ Connected")
        else:
            st.sidebar.write("🤖 Mistral AI: 🔴 Not Configured")
    elif st.session_state.ai_provider == "Ollama":
        if st.session_state.ollama_client:
            # Check specific model availability for a more detailed status
            target_model = "llama3.2" # Primary text model
            vision_model = "llava" # Primary vision model

            text_model_available = st.session_state.ollama_client.is_model_available(target_model)
            vision_model_available = st.session_state.ollama_client.is_model_available(vision_model)

            status_messages = []
            if text_model_available:
                status_messages.append(f"✅ {target_model} ready")
            else:
                status_messages.append(f"⚠️ {target_model} not found")

            if vision_model_available:
                status_messages.append(f"✅ {vision_model} ready")
            else:
                status_messages.append(f"⚠️ {vision_model} not found (for image analysis)")

            combined_status = ", ".join(status_messages)
            st.sidebar.write(f"🤖 Ollama: {combined_status}")
            if not text_model_available or not vision_model_available:
                 st.sidebar.caption("Use Ollama configuration above to download missing models.")

        else:
            st.sidebar.write("🤖 Ollama: 🔴 Service Not Connected/Configured")

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
    try:
        if not st.session_state.browser:
            raise Exception("Browser not started")
        
        # Take screenshot
        screenshot_path = st.session_state.browser.take_screenshot()
        add_message("assistant", screenshot_path, "image", "Current page screenshot")
        
        # Detect and highlight elements
        annotated_image_path = st.session_state.element_detector.detect_and_annotate_elements(screenshot_path, st.session_state.browser)
        add_message("assistant", annotated_image_path, "image", "Elements detected and indexed")
        
        # Manage screenshot files after successful operations in try block
        # manage_on_disk_screenshots("screenshots/", MAX_SCREENSHOT_FILES) # REMOVED
        # log_debug_message(f"DEBUG: Called manage_on_disk_screenshots from try block in take_screenshot_and_analyze.") # REMOVED

        return annotated_image_path
        
    except Exception as e:
        error_msg = f"Failed to take screenshot: {str(e)}"
        add_message("assistant", error_msg, "error")
        # Manage screenshot files even if an error occurred, as a raw file might have been saved
        # manage_on_disk_screenshots("screenshots/", MAX_SCREENSHOT_FILES) # REMOVED
        # log_debug_message(f"DEBUG: Called manage_on_disk_screenshots from except block in take_screenshot_and_analyze.") # REMOVED
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
    
    # Log messages after st.set_page_config, as it must be the first Streamlit command.
    # log_debug_message itself ensures 'debug_log_messages' is initialized in session_state.
    # log_debug_message(f"DEBUG_STATE: In main(), AFTER st.set_page_config(), 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
    
    # Dynamic Title based on AI Provider
    app_title = "Web Automation Assistant"
    if st.session_state.get('ai_provider') == "Mistral":
        st.title(f"{app_title} (Mistral Edition)")
        st.subheader("Powered by Mistral AI & Computer Vision")
    elif st.session_state.get('ai_provider') == "Ollama":
        st.title(f"{app_title} (Ollama Edition)")
        st.subheader("Powered by Ollama (llama3.2 & LLaVA) & Computer Vision")
    else:
        st.title(app_title) # Default title
        st.subheader("AI-Powered Web Automation")

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
        active_client = None
        client_name = ""
        if st.session_state.ai_provider == "Mistral":
            active_client = st.session_state.mistral_client
            client_name = "Mistral AI"
        elif st.session_state.ai_provider == "Ollama":
            active_client = st.session_state.ollama_client
            client_name = "Ollama"

        if not active_client:
            add_message("assistant", f"Please configure your {client_name} settings in the sidebar first.", "error")
            st.rerun()
            return

        if not st.session_state.browser:
            add_message("assistant", "Please start the browser first using the sidebar controls.", "error")
            # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at Browser prerequisite failed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
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
            active_client = None
            client_name = ""
            planning_model = "" # Define a variable for the model used in planning

            if st.session_state.ai_provider == "Mistral":
                active_client = st.session_state.mistral_client
                client_name = "Mistral AI"
                planning_model = "pixtral-large-latest" # Mistral's model for planning
                if not active_client:
                    add_message("assistant", "Mistral client not initialized. Cannot generate steps.", "error")
                    st.rerun()
                    return
            elif st.session_state.ai_provider == "Ollama":
                active_client = st.session_state.ollama_client
                client_name = "Ollama"
                planning_model = "llama3.2" # Ollama's model for planning (ensure it's suitable)
                if not active_client:
                    add_message("assistant", "Ollama client not initialized or not reachable. Cannot generate steps.", "error")
                    st.rerun()
                    return

            add_message("assistant", f"🧠 Generating steps with {client_name} ({planning_model})...", "info")

            # Dispatch to the correct client's method
            if st.session_state.ai_provider == "Mistral":
                generated_steps = active_client.generate_steps_for_todo(
                    user_prompt=current_objective_for_planning,
                    model_name=planning_model
                )
            elif st.session_state.ai_provider == "Ollama":
                # OllamaClient's generate_steps_for_todo might have different params or needs specific prompt engineering
                # For now, assuming it takes user_prompt and model_name like Mistral's for consistency
                # This might raise NotImplementedError if not fully implemented in ollama_client.py
                try:
                    generated_steps = active_client.generate_steps_for_todo(
                        task_description=current_objective_for_planning # Assuming this matches OllamaClient's method
                        # model_name=planning_model # model_name is often implicit in Ollama or part of the prompt
                    )
                except NotImplementedError:
                    add_message("assistant", f"Step generation is not yet implemented for Ollama. Cannot proceed with planning.", "error")
                    st.session_state.orchestrator_active = False
                    st.rerun()
                    return
                except Exception as e: # Catch other errors from Ollama client
                    add_message("assistant", f"Error generating steps with Ollama: {e}", "error")
                    st.session_state.orchestrator_active = False
                    st.rerun()
                    return


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
        active_client = None
        client_name = ""
        action_decision_model = ""
        vision_model = ""

        if st.session_state.ai_provider == "Mistral":
            active_client = st.session_state.mistral_client
            client_name = "Mistral AI"
            action_decision_model = "pixtral-large-2411"
            vision_model = "pixtral-12b-2409"
        elif st.session_state.ai_provider == "Ollama":
            active_client = st.session_state.ollama_client
            client_name = "Ollama"
            # These models need to be set based on what's available and suitable in Ollama
            action_decision_model = "llava" # LLaVA for combined image + text reasoning for action
            vision_model = "llava"          # LLaVA for vision-based state analysis
            # If a non-vision model were used for action_decision (e.g. pure llama3.2),
            # it wouldn't be able to use the image directly in its prompt for analyze_and_decide.
            # The current ollama_client.analyze_and_decide assumes a LLaVA-like model.

        if not st.session_state.browser or not active_client:
            add_message("assistant", f"Browser or {client_name} client not initialized. Orchestrator cannot proceed.", "error")
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
                # log_debug_message(f"DEBUG_STATE: Just before st.rerun() at orchestrator action screenshot failed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
                st.rerun()
                return

            try:
                with open(annotated_image_path, 'rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')

                add_message("assistant", f"🤔 Using {client_name} ({action_decision_model}) for action decision...", "thinking")

                if st.session_state.ai_provider == "Mistral":
                    response = active_client.analyze_and_decide(
                        image_data, current_task, model_name=action_decision_model, current_context=st.session_state.todo_objective
                    )
                elif st.session_state.ai_provider == "Ollama":
                    try:
                        # Ollama's analyze_and_decide is expected to use a LLaVA model.
                        # It takes image_path, current_task, and current_objective.
                        response = active_client.analyze_and_decide(
                            image_path=annotated_image_path,
                            current_task=current_task,
                            current_objective=st.session_state.todo_objective, # Pass the main objective
                            model_name=action_decision_model
                        )
                    except NotImplementedError: # Should not happen if OllamaClient is correctly implemented
                        add_message("assistant", f"Action decision (analyze_and_decide) is not available for {client_name}. Cannot proceed.", "error")
                        st.session_state.orchestrator_active = False
                        st.rerun()
                        return
                    except Exception as e:
                        add_message("assistant", f"Error during action decision with Ollama: {e}", "error")
                        st.session_state.orchestrator_active = False
                        st.rerun()
                        return

                thinking = response.get('thinking', 'AI provided no reasoning for the action.')
                action_str = response.get('action', '')

                # Use a more generic message for thinking, or specify provider
                thinking_prefix = f"**{client_name} ({action_decision_model}) Reasoning:**"
                add_message("assistant", f"{thinking_prefix} {thinking}", "thinking")

                if not action_str or action_str.strip() == "": # Check if action_str is empty or just whitespace
                    # Check if 'thinking' contains an error message that might be more informative
                    if "error" in thinking.lower() or (response.get("thinking") and "error" in response.get("thinking").lower()):
                         add_message("assistant", f"{client_name} indicated an error during action decision: {thinking}. Stopping.", "error")
                    else:
                        add_message("assistant", f"{client_name} could not determine a valid action. Thinking: {thinking}. Stopping.", "error")
                    st.session_state.orchestrator_active = False # Stop orchestrator if no action
                    st.rerun()
                    return

                # Log the raw action determined by the model
                # log_debug_message(f"DEBUG_ORCHESTRATOR: Action determined by {client_name} ({action_decision_model}): '{action_str}'") # REMOVED

                # Validate action string format before attempting execution (optional, but good practice)
                # This is a basic check; more sophisticated validation could be added.
                valid_actions = ['click(', 'type(', 'navigate_to(', 'press_key(', 'complete', 'done']
                if not any(action_str.lower().startswith(va) for va in valid_actions):
                    add_message("assistant", f"Warning: Action '{action_str}' from {client_name} might be malformed or not a recognized browser action. Attempting execution anyway.", "info")
                    # Potentially, could decide to stop here if action is clearly invalid to prevent errors.
                    # For now, let execute_browser_action handle it.

                # Proceed with execution
                action_executed_successfully = execute_browser_action(action_str)
                st.session_state.execution_summary.append({"task": current_task, "action_model_used": f"{client_name} ({action_decision_model})", "action": action_str, "executed": action_executed_successfully})
                if len(st.session_state.execution_summary) > MAX_EXECUTION_SUMMARY_ITEMS:
                    st.session_state.execution_summary = st.session_state.execution_summary[-MAX_EXECUTION_SUMMARY_ITEMS:]

                if not action_executed_successfully and action_str.lower() not in ['complete', 'done']:
                     add_message("assistant", f"Action '{action_str}' failed to execute properly. Will re-evaluate state.", "error")
                     # Re-run will happen, and the same task will be picked up. analyze_state_vision will assess new state.
            except ollama.ResponseError as e: # Catch specific Ollama errors if not caught by client
                add_message("assistant", f"Ollama API error during action decision: {str(e)}. Check model '{action_decision_model}'.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return
            except Exception as e:
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

                add_message("assistant", f"🧐 Using {client_name} ({vision_model}) for state analysis...", "info")

                if st.session_state.ai_provider == "Mistral":
                    analysis_result = active_client.analyze_state_vision(
                        image_data_after_action, current_task, st.session_state.todo_objective, model_name=vision_model
                    )
                elif st.session_state.ai_provider == "Ollama":
                    try:
                        # Ollama's analyze_state_vision is expected to use a LLaVA model.
                        # It takes image_path, previous_task, current_task, next_task, and objective.
                        next_task_description = tasks[task_idx + 1] if task_idx + 1 < len(tasks) else "None (last task)"
                        prev_task_description = tasks[task_idx -1] if task_idx > 0 else "None (first task)"

                        analysis_result = active_client.analyze_state_vision(
                            image_path=annotated_image_path_after_action,
                            previous_task=prev_task_description,
                            current_task=current_task,
                            next_task=next_task_description,
                            objective=st.session_state.todo_objective,
                            model_name=vision_model
                        )
                    except NotImplementedError: # Should not happen
                        add_message("assistant", f"State analysis (analyze_state_vision) is not available for {client_name}. Cannot verify step.", "error")
                        st.session_state.orchestrator_active = False
                        st.rerun()
                        return
                    except Exception as e:
                        add_message("assistant", f"Error during state analysis with Ollama: {e}", "error")
                        st.session_state.orchestrator_active = False
                        st.rerun()
                        return

                analysis_summary = analysis_result.get('summary', 'AI provided no summary for the state analysis.')
                vision_prefix = f"**Vision Model ({client_name} - {vision_model}) Analysis:**"
                add_message("assistant", f"{vision_prefix} {analysis_summary}", "info")

                st.session_state.execution_summary.append({"task": current_task, "vision_model_used": f"{client_name} ({vision_model})", "vision_analysis": analysis_result})
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

                    add_message("assistant", f"🧐 Using {client_name} ({vision_model}) for final verification...", "info")

                    prev_task_final = tasks[-1] if tasks else "None"
                    if st.session_state.ai_provider == "Mistral":
                        final_analysis = active_client.analyze_state_vision(
                            final_image_data,
                            "Final objective verification",
                            st.session_state.todo_objective,
                            model_name=vision_model
                        )
                    elif st.session_state.ai_provider == "Ollama":
                        final_analysis = active_client.analyze_state_vision(
                            image_path=final_annotated_image_path,
                            previous_task=prev_task_final, # Context of the last actual task
                            current_task="Final objective verification", # Current action is this verification
                            next_task="None (End of process)",
                            objective=st.session_state.todo_objective,
                            model_name=vision_model
                        )

                    final_summary = final_analysis.get('summary', 'AI provided no summary for the final check.')
                    final_check_prefix = f"**Final Check ({client_name} - {vision_model}):**"
                    add_message("assistant", f"{final_check_prefix} {final_summary}", "info")

                    if final_analysis.get("objective_completed"):
                        add_message("assistant", "🎉 Final verification confirms objective completed!", "success")
                    else:
                        add_message("assistant", "⚠️ Final verification suggests the objective may not be fully met or could not be confirmed.", "error")

                except ollama.ResponseError as e: # Catch specific Ollama errors
                     add_message("assistant", f"Ollama API error during final verification: {str(e)}. Check model '{vision_model}'.", "error")
                except Exception as e:
                    add_message("assistant", f"Error during final verification: {str(e)}", "error")
            else:
                add_message("assistant", "Could not take screenshot for final verification.", "error")

            st.session_state.orchestrator_active = False # End of orchestration
            # log_debug_message(f"DEBUG_STATE: Just before st.rerun() after all tasks processed, 'messages' in session_state: {'messages' in st.session_state}") # REMOVED
            st.rerun()

    # Auto-continue legacy automation if active (and orchestrator is not) - This part can be removed if legacy is fully deprecated.
    # This part was removed in prior refactoring, so no st.rerun() here.

    # Debug Log Expander moved to setup_sidebar()

if __name__ == "__main__":
    main()
