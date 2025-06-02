import streamlit as st
import os
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
from mistral_client import MistralClient
from ollama_client import OllamaClient # Added
from element_detector import ElementDetector
import traceback

def initialize_session_state():
    """Initialize session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'browser' not in st.session_state:
        st.session_state.browser = None

    # LLM Clients and Provider Selection
    if 'selected_provider' not in st.session_state:
        st.session_state.selected_provider = "Mistral" # Default provider
    if 'mistral_client' not in st.session_state:
        st.session_state.mistral_client = None
    if 'ollama_client' not in st.session_state:
        st.session_state.ollama_client = None
    if 'ollama_connected' not in st.session_state: # To track Ollama connection status
        st.session_state.ollama_connected = False

    if 'element_detector' not in st.session_state:
        st.session_state.element_detector = ElementDetector()
    if 'automation_active' not in st.session_state:
        st.session_state.automation_active = False
    if 'current_objective' not in st.session_state:
        st.session_state.current_objective = None


def setup_sidebar():
    """Setup sidebar for API key configuration, provider selection, and controls"""
    st.sidebar.title("🔧 Configuration")

    # LLM Provider Selection
    st.sidebar.subheader("LLM Provider")
    provider_options = ["Mistral", "Ollama Llama2"]
    st.session_state.selected_provider = st.sidebar.selectbox(
        "Choose LLM Provider",
        options=provider_options,
        index=provider_options.index(st.session_state.selected_provider)
    )

    if st.session_state.selected_provider == "Mistral":
        st.sidebar.subheader("Mistral AI API Key")
        api_key = st.sidebar.text_input(
            "API Key",
            value=os.getenv("MISTRAL_API_KEY", ""),
            type="password",
            help="Enter your Mistral AI API key"
        )
        if api_key:
            if st.session_state.mistral_client is None or st.session_state.mistral_client.api_key != api_key:
                try:
                    st.session_state.mistral_client = MistralClient(api_key)
                    if st.session_state.mistral_client.test_connection():
                         st.sidebar.success("✅ Mistral API Key configured and connected.")
                         st.session_state.ollama_client = None # Clear other client
                         st.session_state.ollama_connected = False
                    else:
                        st.session_state.mistral_client = None
                        st.sidebar.error("❌ Failed to connect to Mistral. Check API key and network.")
                except Exception as e:
                    st.session_state.mistral_client = None
                    st.sidebar.error(f"❌ Error configuring Mistral: {str(e)}")
        else:
            st.sidebar.warning("⚠️ Please enter your Mistral AI API key")

    elif st.session_state.selected_provider == "Ollama Llama2":
        st.sidebar.subheader("Ollama Llama2 Configuration")
        ollama_host = st.sidebar.text_input("Ollama Host URL", value="http://localhost:11434", help="URL of your Ollama server.")

        if st.sidebar.button("🔌 Connect to Ollama"):
            try:
                st.session_state.ollama_client = OllamaClient(host=ollama_host, model='llama2') # Specify model
                if st.session_state.ollama_client.test_connection():
                    st.session_state.ollama_connected = True
                    st.session_state.mistral_client = None # Clear other client
                    st.sidebar.success("✅ Connected to Ollama (llama2 model).")
                else:
                    st.session_state.ollama_connected = False
                    st.session_state.ollama_client = None
                    st.sidebar.error("❌ Failed to connect to Ollama or llama2 model not found. Ensure Ollama is running and 'llama2' is pulled.")
            except Exception as e:
                st.session_state.ollama_connected = False
                st.session_state.ollama_client = None
                st.sidebar.error(f"❌ Error connecting to Ollama: {str(e)}")

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
            st.session_state.automation_active = False # Also stop automation
            st.sidebar.success("✅ Browser stopped")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to stop browser: {str(e)}")

    st.sidebar.divider()
    st.sidebar.subheader("Status")
    browser_status = "🟢 Running" if st.session_state.browser else "🔴 Stopped" # Simplified browser status
    st.sidebar.write(f"Browser: {browser_status}")

    api_status = "🔴 Not configured"
    if st.session_state.selected_provider == "Mistral" and st.session_state.mistral_client:
        api_status = "🟢 Mistral Connected"
    elif st.session_state.selected_provider == "Ollama Llama2" and st.session_state.ollama_connected:
        api_status = "🟢 Ollama Connected"
    st.sidebar.write(f"LLM: {api_status}")

def display_chat_history():
    """Display chat message history"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["type"] == "text":
                st.write(message["content"])
            elif message["type"] == "image":
                st.image(message["content"], caption=message.get("caption", "Screenshot"))
            elif message["type"] == "thinking":
                st.info(f"🤔 **Thinking ({st.session_state.get('selected_provider', 'LLM')}):** {message['content']}")
            elif message["type"] == "action":
                st.success(f"⚡ **Action ({st.session_state.get('selected_provider', 'LLM')}):** {message['content']}")
            elif message["type"] == "error":
                st.error(f"❌ **Error:** {message['content']}")

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
        error_msg = f"Failed to take screenshot or analyze elements: {str(e)}"
        add_message("assistant", error_msg, "error")
        return None

def execute_automation_step(user_objective):
    """Execute one step of the automation process using the selected LLM provider"""
    try:
        current_provider = st.session_state.selected_provider
        llm_client = None
        response = None

        if not st.session_state.browser:
            raise Exception("Browser not started")

        if current_provider == "Mistral":
            if not st.session_state.mistral_client:
                raise Exception("Mistral AI client not configured")
            llm_client = st.session_state.mistral_client

            # Mistral uses image analysis
            annotated_image_path = take_screenshot_and_analyze()
            if not annotated_image_path:
                return False # Error already added by take_screenshot_and_analyze

            with open(annotated_image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')

            response = llm_client.analyze_and_decide(
                image_data, user_objective, st.session_state.current_objective
            )

        elif current_provider == "Ollama Llama2":
            if not st.session_state.ollama_client or not st.session_state.ollama_connected:
                raise Exception("Ollama client not configured or not connected. Please connect in the sidebar.")
            llm_client = st.session_state.ollama_client

            # Ollama (Llama2) does not use image analysis in this setup
            # We can take a screenshot for user reference, but it's not sent to Ollama
            if st.session_state.browser:
                 screenshot_path = st.session_state.browser.take_screenshot() # Take screenshot for context
                 add_message("assistant", screenshot_path, "image", "Current page screenshot (not sent to Ollama)")

            add_message("assistant", "Asking Ollama Llama2 for the next step (no image analysis).", "thinking") # Changed from info to thinking type
            response = llm_client.analyze_and_decide(
                user_objective, st.session_state.current_objective
            )
        else:
            raise Exception(f"Unsupported provider: {current_provider}")

        if not response:
             raise Exception("LLM did not return a response.")

        thinking = response.get('thinking', 'No reasoning provided')
        action = response.get('action', 'No action specified')

        add_message("assistant", thinking, "thinking")
        # add_message("assistant", action, "action") # Action message added after successful execution

        # Execute action
        if not action or action.lower() == "no action specified":
            add_message("assistant", "No specific action was specified by the LLM.", "error")
            return True # Continue, maybe next step will be better

        if action.lower().startswith('click('):
            # For Mistral (indexed): click(INDEX)
            # For Ollama (descriptive): click('TEXT_DESCRIPTION')
            target = action.split('(', 1)[1].rsplit(')', 1)[0].strip()

            if current_provider == "Mistral": # Click by index
                try:
                    index = int(target)
                    st.session_state.browser.click_element_by_index(index)
                    add_message("assistant", f"Clicked element at index {index}", "action")
                except ValueError: # Handle case where target is not an int (e.g. if Mistral returns a description)
                    # Try clicking by text description as a fallback for Mistral if index parsing fails
                    try:
                        target_description = target.strip("'"") # Remove potential quotes
                        st.session_state.browser.click_element_by_text(target_description)
                        add_message("assistant", f"Clicked element described as '{target_description}' (Mistral fallback)", "action")
                    except AttributeError:
                        add_message("assistant", f"Action '{action}' requires clicking by text, but 'click_element_by_text' is not implemented in browser_automation.py.", "error")
                        return False
                    except Exception as e_text_click:
                         raise Exception(f"Invalid index '{target}' in Mistral action and fallback click by text also failed: {str(e_text_click)}. Action: {action}")

            else: # Click by text/description for Ollama
                try:
                    target_description = target.strip("'"")
                    st.session_state.browser.click_element_by_text(target_description)
                    add_message("assistant", f"Clicked element described as '{target_description}'", "action")
                except AttributeError:
                     add_message("assistant", f"Action '{action}' requires clicking by text, but 'click_element_by_text' is not implemented in browser_automation.py.", "error")
                     return False
                except Exception as e:
                    add_message("assistant", f"Failed to click element '{target_description}': {str(e)}", "error")
                    return False

        elif action.lower().startswith('type('):
            import re
            # Regex to capture: type("TEXT", into="DESC") or type('TEXT', into='DESC')
            match = re.search(r"type\((['\"])(.*?)\1\s*,\s*into\s*=\s*(['\"])(.*?)\3\)", action, re.IGNORECASE)
            if match:
                text_to_type = match.group(2)
                element_description = match.group(4)
                try:
                    # For Mistral, element_description might be an index if it was trained that way
                    if current_provider == "Mistral":
                        try:
                            element_index = int(element_description)
                            st.session_state.browser.type_text_by_index(text_to_type, element_index)
                            add_message("assistant", f"Typed '{text_to_type}' into element at index {element_index}", "action")
                        except ValueError: # If not an index, assume it's a description
                            st.session_state.browser.type_text_by_description(text_to_type, element_description)
                            add_message("assistant", f"Typed '{text_to_type}' into element described as '{element_description}' (Mistral fallback to description)", "action")
                        except AttributeError as ae_mistral_type:
                             # This error occurs if type_text_by_index or type_text_by_description is missing
                             add_message("assistant", f"Action '{action}' failed. Required method not implemented in browser_automation.py: {str(ae_mistral_type)}", "error")
                             return False

                    else: # For Ollama, element_description is always a text description
                        st.session_state.browser.type_text_by_description(text_to_type, element_description)
                        add_message("assistant", f"Typed '{text_to_type}' into element described as '{element_description}'", "action")

                except AttributeError as ae:
                     # This error occurs if type_text_by_description (or _by_index for Mistral) is missing
                     add_message("assistant", f"Action '{action}' requires typing, but a corresponding method ('type_text_by_description' or 'type_text_by_index') is not implemented in browser_automation.py. Error: {str(ae)}", "error")
                     return False
                except Exception as e:
                    add_message("assistant", f"Failed to type '{text_to_type}' into '{element_description}': {str(e)}", "error")
                    return False
            else:
                raise Exception(f"Invalid type action format: {action}. Expected: type('TEXT', into='ELEMENT_DESCRIPTION') or type('TEXT', into='ELEMENT_INDEX')")
        
        elif 'complete' in action.lower() or 'done' in action.lower():
            st.session_state.automation_active = False
            add_message("assistant", "🎉 Objective completed successfully!")
            return False
        
        else:
            add_message("assistant", f"Unknown or unsupported action: {action}", "error")
            return True

        return True

    except Exception as e:
        error_msg = f"Automation step failed: {str(e)}\n{traceback.format_exc()}"
        add_message("assistant", error_msg, "error")
        st.session_state.automation_active = False
        return False

def main():
    """Main application function"""
    st.set_page_config(
        page_title="Web Automation Assistant",
        page_icon="🤖",
        layout="wide"
    )

    st.title("🤖 Web Automation Assistant")
    st.subheader("Powered by AI & Computer Vision")
    
    initialize_session_state()
    setup_sidebar()
    
    st.write("Enter your automation objective. The assistant will use the selected LLM provider to help you achieve it.")
    display_chat_history()
    
    user_input = st.chat_input("What would you like me to do on the web?")
    
    if user_input:
        add_message("user", user_input)
        
        provider = st.session_state.selected_provider
        llm_ready = False
        if provider == "Mistral":
            if st.session_state.mistral_client:
                llm_ready = True
            else:
                add_message("assistant", "Please configure your Mistral AI API key in the sidebar first.", "error")
        elif provider == "Ollama Llama2":
            if st.session_state.ollama_client and st.session_state.ollama_connected:
                llm_ready = True
            else:
                add_message("assistant", "Please connect to your Ollama server (Llama2 model) in the sidebar first.", "error")

        if not llm_ready:
            st.rerun()
            return
        
        if not st.session_state.browser:
            add_message("assistant", "Please start the browser first using the sidebar controls.", "error")
            st.rerun()
            return

        st.session_state.current_objective = user_input
        st.session_state.automation_active = True
        add_message("assistant", f"Starting automation for: '{user_input}' using {provider}")
        
        # Initialize step count if it's a new objective or automation restarted
        if 'current_step_count' not in st.session_state or not st.session_state.automation_active:
            st.session_state.current_step_count = 0

        if st.session_state.automation_active:
            st.session_state.current_step_count += 1
            add_message("assistant", f"--- Step {st.session_state.current_step_count} ---")

            success = execute_automation_step(user_input)

            if not success or not st.session_state.automation_active:
                st.session_state.automation_active = False
                add_message("assistant", "Automation stopped due to error or completion.")
                if 'current_step_count' in st.session_state:
                    del st.session_state.current_step_count
            elif st.session_state.current_step_count >= 20: # Max steps
                add_message("assistant", "Maximum steps (20) reached. Stopping automation.", "error")
                st.session_state.automation_active = False
                if 'current_step_count' in st.session_state:
                    del st.session_state.current_step_count

            st.rerun()

if __name__ == "__main__":
    main()
