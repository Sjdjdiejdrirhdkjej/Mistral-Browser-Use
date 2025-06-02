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
    # Initializes session state variables including llm_client, selected_provider, ollama_url, mistral_api_key
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'browser' not in st.session_state:
        st.session_state.browser = None
    if 'llm_client' not in st.session_state:
        st.session_state.llm_client = None
    if 'element_detector' not in st.session_state:
        st.session_state.element_detector = ElementDetector()
    if 'automation_active' not in st.session_state:
        st.session_state.automation_active = False
    if 'current_objective' not in st.session_state:
        st.session_state.current_objective = None
    if 'selected_provider' not in st.session_state:
        st.session_state.selected_provider = os.getenv("DEFAULT_PROVIDER", "Mistral")
    if 'ollama_url' not in st.session_state:
        st.session_state.ollama_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    if 'mistral_api_key' not in st.session_state:
        st.session_state.mistral_api_key = os.getenv("MISTRAL_API_KEY", "")

def setup_sidebar():
    st.sidebar.title("🔧 Configuration")

    st.sidebar.subheader("AI Provider")
    provider_options = ["Mistral", "Ollama"]
    
    # Store current provider to detect change
    prev_provider = st.session_state.selected_provider
    st.session_state.selected_provider = st.sidebar.selectbox(
        "Choose AI Provider",
        options=provider_options,
        index=provider_options.index(st.session_state.selected_provider),
        key="provider_select"
    )

    # If provider changed, invalidate old client
    if prev_provider != st.session_state.selected_provider:
        st.session_state.llm_client = None
        # Clear previous provider's potentially sensitive info from direct display if necessary,
        # though here we rely on conditional display.

    if st.session_state.selected_provider == "Mistral":
        st.sidebar.subheader("Mistral AI Configuration")
        current_api_key = st.session_state.mistral_api_key
        new_api_key = st.sidebar.text_input(
            "API Key",
            value=current_api_key,
            type="password",
            help="Enter your Mistral AI API key",
            key="mistral_api_key_field"
        )
        if new_api_key != current_api_key:
            st.session_state.mistral_api_key = new_api_key
            st.session_state.llm_client = None # Invalidate on key change

        if st.session_state.mistral_api_key:
            if not isinstance(st.session_state.llm_client, MistralClient): # Only init if not already correct type or None
                try:
                    st.session_state.llm_client = MistralClient(api_key=st.session_state.mistral_api_key)
                    # Success message can be shown once after initialization, not every rerun
                    if prev_provider != "Mistral" or new_api_key != current_api_key :
                         st.sidebar.success("✅ Mistral Client Initialized")
                except ValueError as e:
                    st.sidebar.error(f"❌ Mistral Error: {str(e)}")
                    st.session_state.llm_client = None
        else:
            if isinstance(st.session_state.llm_client, MistralClient): st.session_state.llm_client = None
            st.sidebar.warning("⚠️ Please enter your Mistral AI API key.")

    elif st.session_state.selected_provider == "Ollama":
        st.sidebar.subheader("Ollama Configuration")
        current_ollama_url = st.session_state.ollama_url
        new_ollama_url = st.sidebar.text_input(
            "Ollama Server URL",
            value=current_ollama_url,
            help="E.g., http://localhost:11434",
            key="ollama_url_field"
        )
        if new_ollama_url != current_ollama_url:
            st.session_state.ollama_url = new_ollama_url
            st.session_state.llm_client = None # Invalidate on URL change

        if st.sidebar.button("Connect to Ollama", key="ollama_connect_button"):
            if st.session_state.ollama_url:
                try:
                    # Always attempt to create and test client on button press
                    client = OllamaClient(host=st.session_state.ollama_url)
                    if client.test_connection():
                        st.session_state.llm_client = client
                        st.sidebar.success("✅ Ollama connected successfully!")
                    else:
                        st.session_state.llm_client = None
                        st.sidebar.error("❌ Failed to connect to Ollama. Check URL/server.")
                except Exception as e:
                    st.session_state.llm_client = None
                    st.sidebar.error(f"❌ Connection error: {str(e)}")
            else:
                st.sidebar.warning("⚠️ Please enter the Ollama Server URL.")

        if not st.session_state.ollama_url: # This check might be redundant if button is primary trigger
            if isinstance(st.session_state.llm_client, OllamaClient): st.session_state.llm_client = None
            st.sidebar.warning("⚠️ Enter Ollama URL and click Connect.")
        elif st.session_state.ollama_url and not st.session_state.llm_client: # If URL is set but client not (e.g. after failed attempt or URL change)
             st.sidebar.info("Click 'Connect to Ollama' to establish connection.")


    st.sidebar.divider()
    st.sidebar.subheader("Browser Controls")
    if st.sidebar.button("🚀 Start Browser", disabled=st.session_state.automation_active, key="start_browser_button"):
        try:
            st.session_state.browser = BrowserAutomation()
            st.session_state.browser.start_browser()
            st.sidebar.success("✅ Browser started")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to start browser: {str(e)}")

    if st.sidebar.button("🛑 Stop Browser", disabled=(not st.session_state.browser), key="stop_browser_button"):
        try:
            if st.session_state.browser:
                st.session_state.browser.close()
                st.session_state.browser = None
            st.session_state.automation_active = False
            st.sidebar.success("✅ Browser stopped")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to stop browser: {str(e)}")

    st.sidebar.divider()
    st.sidebar.subheader("Status")
    browser_status = "🟢 Running" if st.session_state.browser else "🔴 Stopped"
    st.sidebar.write(f"Browser: {browser_status}")

    ai_status = "🔴 Not Configured"
    if st.session_state.llm_client:
        if isinstance(st.session_state.llm_client, MistralClient) and st.session_state.selected_provider == "Mistral":
            ai_status = "🟢 Mistral Configured"
        elif isinstance(st.session_state.llm_client, OllamaClient) and st.session_state.selected_provider == "Ollama":
            ai_status = "🟢 Ollama Connected"
        # If client type and selected provider mismatch, it implies state needs reset for that provider
        elif st.session_state.selected_provider == "Mistral":
             ai_status = "🔴 Mistral Not Configured"
             if isinstance(st.session_state.llm_client, OllamaClient): st.session_state.llm_client = None # Clear wrong client
        elif st.session_state.selected_provider == "Ollama":
             ai_status = "🔴 Ollama Not Configured"
             if isinstance(st.session_state.llm_client, MistralClient): st.session_state.llm_client = None # Clear wrong client
    else: # No client exists
        ai_status = f"🔴 {st.session_state.selected_provider} Not Configured"
    st.sidebar.write(f"AI Provider: {ai_status}")

def display_chat_history():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["type"] == "text": st.write(message["content"])
            elif message["type"] == "image": st.image(message["content"], caption=message.get("caption", "Screenshot"))
            elif message["type"] == "thinking": st.info(f"🤔 **Thinking:** {message['content']}")
            elif message["type"] == "action": st.success(f"⚡ **Action:** {message['content']}")
            elif message["type"] == "error": st.error(f"❌ **Error:** {message['content']}")

def add_message(role, content, msg_type="text", caption=None):
    message = {"role": role, "type": msg_type, "content": content, "timestamp": datetime.now()}
    if caption: message["caption"] = caption
    st.session_state.messages.append(message)

def take_screenshot_and_analyze():
    try:
        if not st.session_state.browser: raise Exception("Browser not started")
        screenshot_path = st.session_state.browser.take_screenshot()
        add_message("assistant", screenshot_path, "image", "Current page screenshot")
        annotated_image_path = st.session_state.element_detector.detect_and_annotate_elements(screenshot_path, st.session_state.browser)
        add_message("assistant", annotated_image_path, "image", "Elements detected and indexed")
        return annotated_image_path
    except Exception as e:
        add_message("assistant", f"Failed to take screenshot: {str(e)}", "error")
        return None

def execute_automation_step(user_objective):
    try:
        if not st.session_state.llm_client:
            raise Exception(f"{st.session_state.selected_provider} provider not configured. Please configure it in the sidebar.")
        if not st.session_state.browser: raise Exception("Browser not started")
        
        annotated_image_path = take_screenshot_and_analyze()
        if not annotated_image_path: return False
        
        with open(annotated_image_path, 'rb') as img_file:
            image_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        # Use the generic llm_client
        response = st.session_state.llm_client.analyze_and_decide(
            image_data, user_objective, st.session_state.current_objective
        )
        
        thinking = response.get('thinking', 'No reasoning provided')
        action = response.get('action', 'No action specified')
        add_message("assistant", thinking, "thinking")
        add_message("assistant", action, "action")
        
        if action.lower().startswith('click('):
            index_str = action.split('(')[1].split(')')[0]
            try:
                index = int(index_str)
                st.session_state.browser.click_element_by_index(index)
                add_message("assistant", f"Clicked element at index {index}")
            except ValueError: raise Exception(f"Invalid index in action: {action}")
        elif action.lower().startswith('type('):
            import re
            match = re.search(r"type\(['\"](.*?)['\"]\s*,\s*into\s*=\s*['\"](.*?)['\"]\)", action)
            if match:
                text_to_type, element_desc = match.group(1), match.group(2)
                st.session_state.browser.type_text(text_to_type, element_desc)
                add_message("assistant", f"Typed '{text_to_type}' into {element_desc}")
            else: raise Exception(f"Invalid type action format: {action}")
        elif 'complete' in action.lower() or 'done' in action.lower():
            st.session_state.automation_active = False
            add_message("assistant", "🎉 Objective completed successfully!")
            return False
        else: # Fallback for unknown actions or direct index clicks
            try:
                index = int(action) # Try to interpret the action as a direct index
                st.session_state.browser.click_element_by_index(index)
                add_message("assistant", f"Clicked element at index {index} (inferred from action)")
            except ValueError:
                 add_message("assistant", f"Unknown or unhandled action: {action}", "error")
        return True
    except Exception as e:
        error_msg = f"Automation step failed: {str(e)}\n{traceback.format_exc()}"
        add_message("assistant", error_msg, "error")
        st.session_state.automation_active = False
        return False

def main():
    st.set_page_config(page_title="Web Automation Assistant", page_icon="🤖", layout="wide")
    st.title("🤖 Web Automation Assistant")
    st.subheader("Powered by AI & Computer Vision")
    
    initialize_session_state()
    setup_sidebar()
    
    st.write("Enter your automation objective and I'll help you navigate the web!")
    display_chat_history()
    
    user_input = st.chat_input("What would you like me to do on the web?")
    
    if user_input:
        add_message("user", user_input)
        if not st.session_state.llm_client:
            add_message("assistant", f"Please configure the {st.session_state.selected_provider} provider in the sidebar first.", "error")
            st.rerun(); return
        if not st.session_state.browser:
            add_message("assistant", "Please start the browser using sidebar controls.", "error")
            st.rerun(); return
        
        st.session_state.current_objective = user_input
        st.session_state.automation_active = True
        add_message("assistant", f"Starting automation for: {user_input} using {st.session_state.selected_provider}")
        
        max_steps, step_count = 20, 0
        while st.session_state.automation_active and step_count < max_steps:
            step_count += 1
            add_message("assistant", f"--- Step {step_count} ---")
            if not execute_automation_step(user_input):
                st.session_state.automation_active = False; break
            time.sleep(2)
        
        if step_count >= max_steps and st.session_state.automation_active:
            add_message("assistant", "Max steps reached. Stopping.", "error")
            st.session_state.automation_active = False
        if st.session_state.automation_active: # If loop finished otherwise
             st.session_state.automation_active = False
             add_message("assistant", "Automation loop finished.", "info")
        st.rerun()

if __name__ == "__main__":
    main()
