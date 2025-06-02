import streamlit as st
import os
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
# import streamlit as st # Ensure streamlit is imported if not already fully at the top # Redundant
# import os # Redundant
# import time # Ensure time is imported # Redundant
# import base64 # Redundant
# from datetime import datetime # Redundant
# from browser_automation import BrowserAutomation # Redundant
from mistral_client import MistralClient
from ollama_client import (
    OllamaClient, start_ollama_server, is_ollama_server_responsive,
    stop_ollama_server, pull_model_via_ollama,
    check_model_pulled_via_ollama_api, get_ollama_model_file_path
)
# from local_llm_client import LlamaIndexLocalClient # Import LlamaIndexLocalClient # Commented out
from element_detector import ElementDetector
import todo_manager
import traceback
import re # Added import

def initialize_session_state():
    """Initialize session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'providers' not in st.session_state: # Add providers dictionary
        st.session_state.providers = {}
    if 'browser' not in st.session_state:
        st.session_state.browser = None
    if 'mistral_client' not in st.session_state: # Legacy, aim to phase out direct use
        st.session_state.mistral_client = None
    # Removed st.session_state.ollama_client as it's accessed via providers
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

    # Initialize OllamaClient
    if 'ollama' not in st.session_state.providers:
        try:
            st.session_state.providers['ollama'] = OllamaClient()
            print("OllamaClient initialized successfully during session init.")
        except Exception as e:
            print(f"Failed to initialize OllamaClient during session init: {e}")
            st.session_state.providers['ollama'] = None

    # Initialize MistralClient from environment variable
    if 'mistral' not in st.session_state.providers:
        try:
            api_key_env = os.getenv("MISTRAL_API_KEY")
            if api_key_env:
                st.session_state.providers['mistral'] = MistralClient(api_key=api_key_env)
                st.session_state.mistral_client = st.session_state.providers['mistral'] # Sync legacy
                print("MistralClient initialized successfully from env var during session init.")
            else:
                st.session_state.providers['mistral'] = None
                print("Mistral API key not found in env vars during session init.")
        except Exception as e:
            print(f"Failed to initialize MistralClient from env var during session init: {e}")
            st.session_state.providers['mistral'] = None

    if 'selected_provider' not in st.session_state:
        st.session_state.selected_provider = 'Mistral' # Default provider

    # Mapping for provider selection - ensure this is always set
    st.session_state.provider_mapping = {
        'Mistral': 'mistral',
        'Ollama (Official API)': 'ollama', # Renamed for clarity
        # 'Ollama (Local Llama2 via LlamaIndex)': 'ollama_local_llaindex' # Commented out
    }
    # Active provider key initialization - ensure this is always set after selected_provider and mapping
    st.session_state.active_provider_key = st.session_state.provider_mapping.get(st.session_state.selected_provider, 'mistral') # Default to mistral key

    # New session state variables for Ollama local LlamaIndex setup (Commented out if specific)
    # These are specific to the local LlamaIndex flow, so they can be commented.
    # if 'ollama_server_status' not in st.session_state:
    #     st.session_state.ollama_server_status = 'stopped'
    # if 'llama2_pull_status' not in st.session_state:
    #     st.session_state.llama2_pull_status = 'not_pulled'
    # if 'local_model_file_path' not in st.session_state:
    #     st.session_state.local_model_file_path = None
    # if 'local_llm_client_status' not in st.session_state:
    #     st.session_state.local_llm_client_status = 'not_initialized'
    # if 'ollama_local_setup_stage' not in st.session_state:
    #     st.session_state.ollama_local_setup_stage = 'initial'
    # if 'ollama_popen_handle' not in st.session_state:
    #     st.session_state.ollama_popen_handle = None
    # Note: ollama_server_status might be used by the regular Ollama (Official API) if it implies server management.
    # For now, assuming it was primarily for the local setup flow. If the regular Ollama provider needs it,
    # it should be kept. The subtask implies these are specific to local LlamaIndex.
    # Let's assume 'ollama_server_status', 'llama2_pull_status' are specific and comment them.
    # 'local_model_file_path', 'local_llm_client_status', 'ollama_local_setup_stage', 'ollama_popen_handle' are definitely specific.

    if 'ollama_server_status' not in st.session_state : # Keep if potentially shared
        st.session_state.ollama_server_status = 'stopped' # Or ensure it's initialized if used by official Ollama too

    if 'llama2_pull_status' not in st.session_state : # Keep if potentially shared for official ollama
         st.session_state.llama2_pull_status = 'not_pulled'


    # These are definitely specific to the local LlamaIndex flow.
    # if 'local_model_file_path' not in st.session_state: # Commenting out
    #     st.session_state.local_model_file_path = None
    # if 'local_llm_client_status' not in st.session_state: # Commenting out
    #     st.session_state.local_llm_client_status = 'not_initialized'
    # if 'ollama_local_setup_stage' not in st.session_state: # Commenting out
    #     st.session_state.ollama_local_setup_stage = 'initial'
    # if 'ollama_popen_handle' not in st.session_state: # Commenting out
    #     st.session_state.ollama_popen_handle = None


def setup_sidebar():
    """Setup sidebar for API key configuration and controls"""
    st.sidebar.title("🔧 Configuration")

    # Provider Selection
    st.sidebar.subheader("AI Provider")
    provider_options = list(st.session_state.provider_mapping.keys()) # Use keys from mapping
    
    # Adjust index if selected_provider is no longer in options
    current_selection = st.session_state.selected_provider
    if current_selection not in provider_options:
        st.session_state.selected_provider = 'Mistral' # Default to Mistral if previous selection is removed
        st.session_state.active_provider_key = st.session_state.provider_mapping[st.session_state.selected_provider]


    selected_provider_display_name = st.sidebar.radio(
        "Choose AI Provider:",
        options=provider_options,
        index=provider_options.index(st.session_state.selected_provider),
        key='selected_provider_radio_widget'
    )

    if st.session_state.selected_provider != selected_provider_display_name:
        st.session_state.selected_provider = selected_provider_display_name
        st.session_state.active_provider_key = st.session_state.provider_mapping[selected_provider_display_name]
        # st.rerun()

    if st.session_state.selected_provider == 'Mistral':
        st.sidebar.subheader("Mistral AI API Key")
        api_key = st.sidebar.text_input(
            "API Key",
            value=os.getenv("MISTRAL_API_KEY", ""),
            type="password",
            help="Enter your Mistral AI API key"
        )

        if api_key:
            current_mistral_client = st.session_state.providers.get('mistral')
            if not isinstance(current_mistral_client, MistralClient) or current_mistral_client.api_key != api_key:
                try:
                    st.session_state.providers['mistral'] = MistralClient(api_key=api_key)
                    st.session_state.mistral_client = st.session_state.providers['mistral']
                    st.sidebar.success("✅ Mistral API Key configured")
                    print("MistralClient re-initialized/updated via sidebar.")
                except Exception as e:
                    st.sidebar.error(f"❌ Failed to initialize Mistral Client: {e}")
                    st.session_state.providers['mistral'] = None
                    st.session_state.mistral_client = None
        elif not st.session_state.providers.get('mistral'):
            st.sidebar.warning("⚠️ Please enter your Mistral AI API key to use Mistral.")
            st.session_state.providers['mistral'] = None
            st.session_state.mistral_client = None

    elif st.session_state.selected_provider == 'Ollama (Official API)':
        st.sidebar.info("ℹ️ Using Ollama via its official API. Ensure Ollama server is running and accessible.")
        if not st.session_state.providers.get('ollama'):
            try:
                st.session_state.providers['ollama'] = OllamaClient()
                print("OllamaClient (Official API) initialized/re-initialized via sidebar.")
                if st.session_state.providers['ollama'].list_models() is not None:
                    st.sidebar.success("✅ Ollama (Official API) client connected.")
                else:
                    st.sidebar.warning("⚠️ Ollama (Official API) client might not be connected.")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to connect to Ollama (Official API): {e}")
                st.session_state.providers['ollama'] = None

    # Commented out block for 'Ollama (Local Llama2 via LlamaIndex)'
    # elif st.session_state.selected_provider == 'Ollama (Local Llama2 via LlamaIndex)':
    #     st.sidebar.subheader("Local Llama2 Setup (via LlamaIndex)")
    #     st.sidebar.info("Follow these steps to set up and use a local Llama2 model with LlamaIndex.")

    #     # Stage: Initial / Server Management
    #     st.sidebar.markdown("**Step 1: Ollama Server Management**")
    #     st.sidebar.write(f"Server Status: `{st.session_state.ollama_server_status}`")

    #     if st.session_state.ollama_server_status == 'starting':
    #         with st.spinner("Starting Ollama server..."):
    #             if start_ollama_server():
    #                 st.session_state.ollama_server_status = 'running'
    #                 st.session_state.ollama_local_setup_stage = 'server_started'
    #             else:
    #                 st.session_state.ollama_server_status = 'failed_to_start'
    #             st.experimental_rerun()
    #     elif st.session_state.ollama_server_status in ['stopped', 'failed_to_start', 'server_stopped_after_pull']:
    #         if st.sidebar.button("Start Ollama Server", key="start_ollama_srv_btn"):
    #             st.session_state.ollama_server_status = 'starting'
    #             st.experimental_rerun()
    #     elif st.session_state.ollama_server_status == 'running':
    #         st.sidebar.success("✅ Ollama Server is running.")
    #     elif st.session_state.ollama_server_status == 'stopping':
    #         with st.spinner("Stopping Ollama server..."):
    #             if stop_ollama_server():
    #                 st.session_state.ollama_server_status = 'stopped'
    #                 if st.session_state.ollama_local_setup_stage == 'model_pulled':
    #                     st.session_state.ollama_local_setup_stage = 'server_stopped_after_pull'
    #                 else:
    #                     st.session_state.ollama_local_setup_stage = 'initial'
    #             else:
    #                 st.session_state.ollama_server_status = 'failed_to_stop'
    #                 st.error("Failed to stop Ollama server.")
    #             st.experimental_rerun()

    #     # Stage: Model Pulling
    #     if st.session_state.ollama_server_status == 'running' and \
    #        st.session_state.ollama_local_setup_stage in ['initial', 'server_started']:
    #         st.sidebar.markdown("**Step 2: Pull Llama2 Model**")
    #         st.sidebar.write(f"Llama2 Pull Status: `{st.session_state.llama2_pull_status}`")

    #         if st.session_state.llama2_pull_status == 'pulling':
    #             with st.spinner("Pulling llama2 model... This can take a while."):
    #                 success, message = pull_model_via_ollama('llama2')
    #                 if success:
    #                     st.session_state.llama2_pull_status = 'pulled'
    #                     st.session_state.ollama_local_setup_stage = 'model_pulled'
    #                 else:
    #                     st.session_state.llama2_pull_status = 'failed'
    #                     st.error(message)
    #                 st.experimental_rerun()
    #         elif st.session_state.llama2_pull_status in ['not_pulled', 'failed']:
    #             if st.sidebar.button("Pull Llama2 Model via Ollama", key="pull_llama2_btn"):
    #                 st.session_state.llama2_pull_status = 'pulling'
    #                 st.experimental_rerun()
    #         elif st.session_state.llama2_pull_status == 'pulled':
    #             st.sidebar.success("✅ Llama2 model pulled successfully.")
    #             st.session_state.ollama_local_setup_stage = 'model_pulled'

    #     # Stage: Server Shutdown (Optional after pull)
    #     if st.session_state.ollama_local_setup_stage == 'model_pulled' and st.session_state.ollama_server_status == 'running':
    #         st.sidebar.markdown("**Step 3: Stop Ollama Server (Recommended)**")
    #         if st.sidebar.button("Stop Ollama Server", key="stop_ollama_srv_btn_after_pull"):
    #             st.session_state.ollama_server_status = 'stopping'
    #             st.experimental_rerun()

    #     # Stage: Model File Location & LlamaIndex Client Initialization
    #     if st.session_state.ollama_local_setup_stage in ['model_pulled', 'server_stopped_after_pull', 'model_path_found'] or \
    #        (st.session_state.llama2_pull_status == 'pulled' and st.session_state.ollama_server_status != 'running'):
    #         if st.session_state.ollama_server_status == 'running' and st.session_state.ollama_local_setup_stage == 'model_pulled':
    #              st.sidebar.warning("Recommendation: Stop Ollama server (Step 3) before initializing LlamaIndex client if Ollama server was used for pulling.")

    #         st.sidebar.markdown("**Step 4: Initialize LlamaIndex Client**")
    #         st.sidebar.write(f"LlamaIndex Client Status: `{st.session_state.local_llm_client_status}`")

    #         if st.session_state.local_llm_client_status == 'initializing':
    #             with st.spinner("Locating model file and initializing LlamaIndex client..."):
    #                 path, msg = get_ollama_model_file_path('llama2')
    #                 if path:
    #                     st.session_state.local_model_file_path = path
    #                     st.sidebar.info(f"Model file found: {path}")
    #                     if 'ollama_local_llaindex' not in st.session_state.providers:
    #                          st.session_state.providers['ollama_local_llaindex'] = None
    #                     client = LlamaIndexLocalClient(model_path=path)
    #                     if client.is_initialized:
    #                         st.session_state.providers['ollama_local_llaindex'] = client
    #                         st.session_state.local_llm_client_status = 'initialized'
    #                         st.session_state.ollama_local_setup_stage = 'llm_initialized'
    #                         st.success("LlamaIndex client initialized successfully!")
    #                     else:
    #                         st.session_state.local_llm_client_status = 'failed'
    #                         st.error("Failed to initialize LlamaIndex client with the model file.")
    #                 else:
    #                     st.session_state.local_llm_client_status = 'failed'
    #                     st.error(f"Failed to locate Llama2 model file: {msg}")
    #                 st.experimental_rerun()

    #         elif st.session_state.local_llm_client_status in ['not_initialized', 'failed']:
    #             if st.sidebar.button("Locate Model & Init LlamaIndex Client", key="init_llaindex_btn"):
    #                 if st.session_state.llama2_pull_status != 'pulled':
    #                     st.sidebar.error("Llama2 model does not seem to be pulled. Please complete Step 2 first.")
    #                 elif st.session_state.ollama_server_status == 'running' and st.session_state.ollama_local_setup_stage not in ['model_pulled_server_already_stopped']:
    #                     st.sidebar.warning("Please stop the Ollama server (Step 3) before initializing the LlamaIndex client if the server was used for pulling.")
    #                 else:
    #                     st.session_state.local_llm_client_status = 'initializing'
    #                     st.experimental_rerun()

    #         elif st.session_state.local_llm_client_status == 'initialized':
    #             st.sidebar.success("✅ LlamaIndex Client is initialized.")
    #             st.session_state.ollama_local_setup_stage = 'llm_initialized'

    #     # Final Stage: Ready
    #     if st.session_state.ollama_local_setup_stage == 'llm_initialized':
    #         st.sidebar.success("✅ Ollama (Local Llama2 via LlamaIndex) is ready!")
    #         if st.session_state.active_provider_key != 'ollama_local_llaindex':
    #             pass


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
    # st.sidebar.subheader("Status") # Combined with provider status

    browser_status = "🟢 Running" if st.session_state.browser and st.session_state.automation_active else "🔴 Stopped"
    st.sidebar.write(f"Browser: {browser_status}")

    active_provider_key = st.session_state.active_provider_key
    client_instance = st.session_state.providers.get(active_provider_key)

    st.sidebar.subheader(f"Status ({st.session_state.selected_provider})")

    if active_provider_key == 'mistral':
        api_status = "🟢 Connected" if client_instance and getattr(client_instance, 'api_key', None) else "🔴 Not configured"
        st.sidebar.write(f"Mistral Client: {api_status}")
    elif active_provider_key == 'ollama':
        ollama_status = "🟢 Connected" if client_instance and client_instance.list_models() is not None else "🔴 Not connected/configured"
        st.sidebar.write(f"Ollama API Client: {ollama_status}")
    # Commented out status for 'ollama_local_llaindex'
    # elif active_provider_key == 'ollama_local_llaindex':
    #     local_llm_status = "🟢 Initialized" if client_instance and getattr(client_instance, 'is_initialized', False) else "🔴 Not initialized"
    #     st.sidebar.write(f"Local LlamaIndex Client: {local_llm_status}")
    #     if st.session_state.ollama_local_setup_stage != 'llm_initialized':
    #          st.sidebar.warning("Setup for Local Llama2 not complete.")


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
            elif message["type"] == "plan":
                st.markdown(message["content"])
            elif message["type"] == "info":
                st.info(f"ℹ️ {message['content']}")
            elif message["type"] == "success":
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

        screenshot_path = st.session_state.browser.take_screenshot()
        add_message("assistant", screenshot_path, "image", "Current page screenshot")

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
    
    st.write("Enter your automation objective and I'll help you navigate the web!")

    display_chat_history()
    
    user_input = st.chat_input("What would you like me to do on the web?")
    
    if user_input:
        add_message("user", user_input)
        
        active_provider_key = st.session_state.active_provider_key
        active_client = st.session_state.providers.get(active_provider_key)

        if not active_client:
            add_message("assistant", f"The selected AI provider ({st.session_state.selected_provider}) is not configured. Please check the sidebar.", "error")
            st.rerun()
            return
        
        if not st.session_state.browser:
            add_message("assistant", "Please start the browser first using the sidebar controls.", "error")
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

        try:
            active_client = st.session_state.providers.get(st.session_state.active_provider_key)
            if not active_client: # Should be caught above, but as a safeguard
                add_message("assistant", f"AI provider '{st.session_state.selected_provider}' not available. Cannot generate steps.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return

            step_generation_model = "pixtral-large-latest"
            if st.session_state.active_provider_key == 'ollama_local_llaindex': # Use LlamaIndex client default model
                step_generation_model = None # LlamaIndexLocalClient methods don't take model_name currently

            add_message("assistant", f"🧠 Generating steps with {st.session_state.selected_provider}...", "info")

            generated_steps = []
            if hasattr(active_client, 'generate_steps_for_todo'):
                if st.session_state.active_provider_key == 'ollama_local_llaindex':
                     generated_steps = active_client.generate_steps_for_todo(task_description=user_input)
                else: # Mistral or Ollama Official
                    generated_steps = active_client.generate_steps_for_todo(
                        user_prompt=user_input,
                        model_name=step_generation_model
                    )
            elif st.session_state.active_provider_key == 'ollama': # Fallback for official Ollama API client
                ollama_prompt = f"Given the objective: '{user_input}', break it down into a numbered list of actionable steps for web automation. Output only the list."
                response_text = active_client.generate_completion(prompt=ollama_prompt, model_name="llama2")
                if response_text:
                    generated_steps = [step.strip() for step in response_text.splitlines() if step.strip() and step.startswith("- ")]
                    generated_steps = [step[2:] for step in generated_steps]
                else:
                    generated_steps = []
            else: # Should not happen if provider is selected and client exists
                generated_steps = []
                add_message("assistant", f"Method 'generate_steps_for_todo' not available for {st.session_state.selected_provider}.", "error")


            if not generated_steps:
                add_message("assistant", "⚠️ Failed to generate steps or no steps were returned. Please try rephrasing your objective.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return

            add_message("assistant", f"✅ Steps generated: {len(generated_steps)} steps.", "success")

            todo_manager.create_todo_file(user_input, generated_steps)
            add_message("assistant", "💾 `todo.md` populated with generated steps.", "info")

            retrieved_todo = todo_manager.read_todo_file()
            st.session_state.todo_objective = retrieved_todo.get("objective")
            st.session_state.todo_tasks = retrieved_todo.get("tasks", [])
            st.session_state.current_task_index = 0

            plan_display_intro = f"**Planning Agent ({st.session_state.selected_provider}) says:** Planning complete. Here's the initial plan:"
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

    if st.session_state.get('orchestrator_active') and st.session_state.todo_tasks:
        active_client = st.session_state.providers.get(st.session_state.active_provider_key)
        if not st.session_state.browser or not active_client:
            add_message("assistant", f"Browser or AI provider '{st.session_state.selected_provider}' not initialized. Orchestrator cannot proceed.", "error")
            st.session_state.orchestrator_active = False
            st.rerun()
            return

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

                action_decision_model = "mistral-small-latest"
                response = {}

                if hasattr(active_client, 'analyze_and_decide'):
                    if st.session_state.active_provider_key == 'ollama_local_llaindex':
                        # LlamaIndexLocalClient.analyze_and_decide takes (analysis_prompt, items_to_consider)
                        # This requires adapting the call or the method signature/logic in LlamaIndexLocalClient
                        # For now, using a generic prompt for it:
                        items_list = [f"Current Task: {current_task}", f"Overall Objective: {st.session_state.todo_objective}"]
                        # The LlamaIndexLocalClient.analyze_and_decide method is not designed for image data.
                        # This path will effectively be text-only for ollama_local_llaindex.
                        # We need a different approach if image analysis is required for LlamaIndexLocalClient.
                        # For now, this will likely not work as expected for UI automation with images.
                        # This highlights a mismatch in capabilities for this specific method.
                        # The prompt needs to guide it to produce thinking and action.
                        decision_prompt = f"Analyze the situation for web automation. Current screenshot shows elements indexed. Your goal is to achieve: '{current_task}' as part of overall objective '{st.session_state.todo_objective}'. Respond with JSON: {{\"thinking\": \"your reasoning\", \"action\": \"CLICK(INDEX) or TYPE('text', 'into') or ...\"}}"
                        if st.session_state.active_provider_key == 'ollama_local_llaindex' and active_client.llm.metadata.model_name == "llava": # Hypothetical check
                             add_message("assistant", "Warning: LlamaIndexLocalClient's analyze_and_decide does not natively support images. This will be text-only analysis for action.", "warning")

                        action_response_text = active_client.analyze_and_decide(analysis_prompt=decision_prompt, items_to_consider=items_list)
                        try:
                            response = json.loads(action_response_text) if action_response_text else {"thinking": "LlamaIndexLocalClient: No response/error", "action": ""}
                        except json.JSONDecodeError:
                            response = {"thinking": f"LlamaIndexLocalClient: Could not parse JSON: {action_response_text}", "action": ""}

                    else: # Mistral or Ollama Official API
                        response = active_client.analyze_and_decide(
                            image_data, current_task, model_name=action_decision_model, current_context=st.session_state.todo_objective
                        )
                elif st.session_state.active_provider_key == 'ollama': # Fallback for official Ollama if no analyze_and_decide
                    ollama_action_prompt = f"""Analyze the screenshot (provided as image data) for the task: '{current_task}' with overall objective '{st.session_state.todo_objective}'.
Respond with a JSON object: {{"thinking": "your reasoning", "action": "CLICK(INDEX) or TYPE('text', 'into') or COMPLETE or NAVIGATE_TO('url')"}}"""
                    action_response_text = active_client.generate_completion(
                        prompt=ollama_action_prompt, model_name="llava", image_base64=image_data
                    )
                    try:
                        response = json.loads(action_response_text) if action_response_text else {"thinking": "Ollama fallback: No response", "action": ""}
                    except json.JSONDecodeError:
                        response = {"thinking": f"Ollama fallback: Could not parse JSON response: {action_response_text}", "action": ""}
                else: # Should not be reached if client exists
                    response = {"thinking": f"Method 'analyze_and_decide' not available for {st.session_state.selected_provider}.", "action": ""}
                    add_message("assistant", response["thinking"], "error")


                thinking = response.get('thinking', 'No reasoning provided for action.')
                action_str = response.get('action', '')
                add_message("assistant", f"**Action Model ({st.session_state.selected_provider}) Reasoning:** {thinking}", "thinking")

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
                analysis_result = {}

                if hasattr(active_client, 'analyze_state_vision'):
                    if st.session_state.active_provider_key == 'ollama_local_llaindex':
                        # LlamaIndexLocalClient.analyze_state_vision takes (prompt, image_url)
                        # image_url is not directly usable unless LlamaCPP model is multimodal and client supports it.
                        # Current LlamaIndexLocalClient.analyze_state_vision is placeholder for images.
                        # This will use the text-only path if image_url is None or not handled.
                        # The prompt needs to guide it for JSON.
                        # This highlights a mismatch in capabilities for this specific method.
                        vision_prompt = f"Analyze the current web page state based on the task '{current_task}' and objective '{st.session_state.todo_objective}'. Respond with JSON: {{\"error\": \"error or null\", \"task_completed\": boolean, \"objective_completed\": boolean, \"summary\": \"page summary\"}}"

                        # Passing image_url=None to use text-only path of analyze_state_vision in LlamaIndexLocalClient
                        # Or, if a multimodal model is loaded, one might try passing the image_data as part of prompt or specific kwarg.
                        # This is a known limitation area.
                        if active_client.llm.metadata.model_name == "llava": # Hypothetical check
                             add_message("assistant", "Warning: LlamaIndexLocalClient's analyze_state_vision with image data is not fully implemented here. Using text prompt.", "warning")

                        vision_response_text = active_client.analyze_state_vision(prompt=vision_prompt, image_url=None) # Effectively text only
                        try:
                            analysis_result = json.loads(vision_response_text) if vision_response_text else {"summary": "LlamaIndexLocalClient: No vision response", "task_completed": False, "objective_completed": False, "error": None}
                        except json.JSONDecodeError:
                            analysis_result = {"summary": f"LlamaIndexLocalClient: Could not parse JSON vision response: {vision_response_text}", "task_completed": False, "objective_completed": False, "error": "JSON Parse Error"}
                    else: # Mistral or Ollama Official API
                        analysis_result = active_client.analyze_state_vision(
                            image_data_after_action, current_task, st.session_state.todo_objective, model_name=vision_model
                        )
                elif st.session_state.active_provider_key == 'ollama': # Fallback for official Ollama
                    ollama_vision_prompt = f"""Analyze the screenshot (image data provided) after an action for task '{current_task}' and objective '{st.session_state.todo_objective}'.
Respond with a JSON object: {{"error": "error message or null", "task_completed": boolean, "objective_completed": boolean, "summary": "page summary"}}"""
                    vision_response_text = active_client.generate_completion(
                        prompt=ollama_vision_prompt, model_name="llava", image_base64=image_data_after_action
                    )
                    try:
                        analysis_result = json.loads(vision_response_text) if vision_response_text else {"summary": "Ollama fallback: No vision response", "task_completed": False, "objective_completed": False, "error": None}
                        analysis_result["task_completed"] = str(analysis_result.get("task_completed", "false")).lower() == "true"
                        analysis_result["objective_completed"] = str(analysis_result.get("objective_completed", "false")).lower() == "true"
                    except json.JSONDecodeError:
                        analysis_result = {"summary": f"Ollama fallback: Could not parse JSON vision response: {vision_response_text}", "task_completed": False, "objective_completed": False, "error": "JSON Parse Error"}
                else: # Should not be reached
                    analysis_result = {"summary": f"Method 'analyze_state_vision' not available for {st.session_state.selected_provider}.", "task_completed": False, "objective_completed": False, "error": "Method not available"}
                    add_message("assistant", analysis_result["summary"], "error")

                analysis_summary = analysis_result.get('summary', 'No analysis summary provided.')
                add_message("assistant", f"**Vision Model ({st.session_state.selected_provider}) Analysis:** {analysis_summary}", "info")
                st.session_state.execution_summary.append({"task": current_task, "vision_analysis": analysis_result})

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

                    vision_model_final = "pixtral-12b-2409"
                    final_analysis = {}
                    if hasattr(active_client, 'analyze_state_vision'):
                        if st.session_state.active_provider_key == 'ollama_local_llaindex':
                            final_vision_prompt = f"Final verification of objective '{st.session_state.todo_objective}'. Respond with JSON: {{\"error\": \"error or null\", \"task_completed\": boolean, \"objective_completed\": boolean, \"summary\": \"page summary\"}}"
                            final_vision_response_text = active_client.analyze_state_vision(prompt=final_vision_prompt, image_url=None) # Text only
                            try:
                                final_analysis = json.loads(final_vision_response_text) if final_vision_response_text else {"summary": "LlamaIndexLocalClient: No final vision response", "objective_completed": False}
                            except json.JSONDecodeError:
                                final_analysis = {"summary": f"LlamaIndexLocalClient: Could not parse JSON final vision response: {final_vision_response_text}", "objective_completed": False}
                        else: # Mistral or Ollama Official
                            final_analysis = active_client.analyze_state_vision(
                                final_image_data, "Final objective verification", st.session_state.todo_objective, model_name=vision_model_final
                            )
                    elif st.session_state.active_provider_key == 'ollama': # Fallback for official Ollama
                         ollama_final_vision_prompt = f"""Final verification of objective '{st.session_state.todo_objective}' based on screenshot.
Respond with JSON: {{"error": "error or null", "task_completed": boolean, "objective_completed": boolean, "summary": "page summary"}}"""
                         final_vision_response_text = active_client.generate_completion(prompt=ollama_final_vision_prompt, model_name="llava", image_base64=final_image_data)
                         try:
                             final_analysis = json.loads(final_vision_response_text) if final_vision_response_text else {"summary": "Ollama fallback: No final vision response", "objective_completed": False}
                             final_analysis["objective_completed"] = str(final_analysis.get("objective_completed", "false")).lower() == "true"
                         except json.JSONDecodeError:
                            final_analysis = {"summary": f"Ollama fallback: Could not parse JSON final vision response: {final_vision_response_text}", "objective_completed": False}
                    else: # Should not be reached
                        final_analysis = {"summary": f"Method 'analyze_state_vision' not available for {st.session_state.selected_provider}.", "objective_completed": False}
                        add_message("assistant", final_analysis["summary"], "error")

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

    if st.session_state.get('automation_active') and not st.session_state.get('orchestrator_active'):
        add_message("assistant", "Legacy automation loop triggered (should be deprecated).", "info")
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()

