import streamlit as st
import os
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
from mistral_client import MistralClient
from element_detector import ElementDetector
import traceback

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
    st.sidebar.write(f"Browser: {browser_status}")
    
    api_status = "🟢 Connected" if st.session_state.mistral_client else "🔴 Not configured"
    st.sidebar.write(f"Mistral AI: {api_status}")

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

def execute_automation_step(user_objective):
    """Execute one step of the automation process"""
    try:
        if not st.session_state.mistral_client:
            raise Exception("Mistral AI client not configured")
        
        if not st.session_state.browser:
            raise Exception("Browser not started")
        
        # Take screenshot and analyze
        annotated_image_path = take_screenshot_and_analyze()
        if not annotated_image_path:
            return False
        
        # Get AI reasoning and action
        with open(annotated_image_path, 'rb') as img_file:
            image_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        response = st.session_state.mistral_client.analyze_and_decide(
            image_data, user_objective, st.session_state.current_objective
        )
        
        # Parse response
        thinking = response.get('thinking', 'No reasoning provided')
        action = response.get('action', 'No action specified')
        
        add_message("assistant", thinking, "thinking")
        add_message("assistant", action, "action")
        
        # Execute action
        if action.lower().startswith('click('):
            # Extract index from click(INDEX)
            index_str = action.split('(')[1].split(')')[0]
            try:
                index = int(index_str)
                st.session_state.browser.click_element_by_index(index)
                add_message("assistant", f"Clicked element at index {index}")
            except ValueError:
                raise Exception(f"Invalid index in action: {action}")
        
        elif action.lower().startswith('type('):
            # Extract text and element from type("TEXT", into="ELEMENT") or type('TEXT', into='ELEMENT')
            import re
            # Match both single and double quotes
            match = re.search(r"type\(['\"](.*?)['\"]\s*,\s*into\s*=\s*['\"](.*?)['\"]\)", action)
            if match:
                text = match.group(1)
                element = match.group(2)
                st.session_state.browser.type_text(text, element)
                add_message("assistant", f"Typed '{text}' into {element}")
            else:
                raise Exception(f"Invalid type action format: {action}")
        
        elif 'complete' in action.lower() or 'done' in action.lower():
            st.session_state.automation_active = False
            add_message("assistant", "🎉 Objective completed successfully!")
            return False
        
        else:
            add_message("assistant", f"Unknown action: {action}", "error")
        
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
    st.subheader("Powered by Mistral AI & Computer Vision")
    
    initialize_session_state()
    setup_sidebar()
    
    # Main chat interface
    st.write("Enter your automation objective and I'll help you navigate the web!")
    
    # Display chat history
    display_chat_history()
    
    # User input
    user_input = st.chat_input("What would you like me to do on the web?")
    
    if user_input:
        add_message("user", user_input)
        
        # Check prerequisites
        if not st.session_state.mistral_client:
            add_message("assistant", "Please configure your Mistral AI API key in the sidebar first.", "error")
            st.rerun()
            return
        
        if not st.session_state.browser:
            add_message("assistant", "Please start the browser first using the sidebar controls.", "error")
            st.rerun()
            return
        
        # Start automation
        st.session_state.current_objective = user_input
        st.session_state.automation_active = True
        
        add_message("assistant", f"Starting automation for: {user_input}")
        
        # Execute automation steps
        max_steps = 20  # Prevent infinite loops
        step_count = 0
        
        while st.session_state.automation_active and step_count < max_steps:
            step_count += 1
            add_message("assistant", f"--- Step {step_count} ---")
            
            success = execute_automation_step(user_input)
            if not success:
                break
            
            time.sleep(2)  # Brief pause between steps
        
        if step_count >= max_steps:
            add_message("assistant", "Maximum steps reached. Stopping automation.", "error")
            st.session_state.automation_active = False
        
        st.rerun()
    
    # Auto-continue automation if active
    if st.session_state.automation_active:
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
