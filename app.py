import streamlit as st
import os
import time
import base64
from datetime import datetime
from browser_automation import BrowserAutomation
from mistral_client import MistralClient
from ollama_client import OllamaClient # Import OllamaClient
from element_detector import ElementDetector
import todo_manager # Added import
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
        'Ollama (Llama2)': 'ollama'
    }
    # Active provider key initialization - ensure this is always set after selected_provider and mapping
    st.session_state.active_provider_key = st.session_state.provider_mapping.get(st.session_state.selected_provider, 'mistral')


def setup_sidebar():
    """Setup sidebar for API key configuration and controls"""
    st.sidebar.title("🔧 Configuration")

    # Provider Selection
    st.sidebar.subheader("AI Provider")
    provider_options = list(st.session_state.provider_mapping.keys()) # Use keys from mapping
    
    selected_provider_display_name = st.sidebar.radio(
        "Choose AI Provider:",
        options=provider_options,
        index=provider_options.index(st.session_state.selected_provider),
        key='selected_provider_radio_widget' # Changed key to avoid conflict if 'selected_provider' is used directly elsewhere
    )

    # Update selected_provider and active_provider_key if the radio button changed
    if st.session_state.selected_provider != selected_provider_display_name:
        st.session_state.selected_provider = selected_provider_display_name
        st.session_state.active_provider_key = st.session_state.provider_mapping[selected_provider_display_name]
        # Potentially trigger a rerun if needed, or handle client initialization here
        # st.rerun() # uncomment if immediate effect of provider switch is needed for other UI parts

    # Conditional API Key Configuration for Mistral
    if st.session_state.selected_provider == 'Mistral':
        st.sidebar.subheader("Mistral AI API Key")
        api_key = st.sidebar.text_input(
            "API Key",
            value=os.getenv("MISTRAL_API_KEY", ""),
            type="password",
            help="Enter your Mistral AI API key"
        )

        if api_key:
            # Initialize or update Mistral client in the providers dictionary
            current_mistral_client = st.session_state.providers.get('mistral')
            if not isinstance(current_mistral_client, MistralClient) or current_mistral_client.api_key != api_key:
                try:
                    st.session_state.providers['mistral'] = MistralClient(api_key=api_key)
                    st.session_state.mistral_client = st.session_state.providers['mistral'] # Sync legacy
                    st.sidebar.success("✅ Mistral API Key configured")
                    print("MistralClient re-initialized/updated via sidebar.")
                except Exception as e:
                    st.sidebar.error(f"❌ Failed to initialize Mistral Client: {e}")
                    st.session_state.providers['mistral'] = None
                    st.session_state.mistral_client = None # Sync legacy
        elif not st.session_state.providers.get('mistral'): # No API key in input and no client in providers
            st.sidebar.warning("⚠️ Please enter your Mistral AI API key to use Mistral.")
            st.session_state.providers['mistral'] = None
            st.session_state.mistral_client = None

    elif st.session_state.selected_provider == 'Ollama (Llama2)':
        st.sidebar.info("ℹ️ Using local Ollama (Llama2). Ensure Ollama is running.")
        if not st.session_state.providers.get('ollama'): # If not initialized successfully during session_state init
            try:
                st.session_state.providers['ollama'] = OllamaClient()
                print("OllamaClient initialized/re-initialized via sidebar.")
                if st.session_state.providers['ollama'].list_models() is not None:
                    st.sidebar.success("✅ Ollama client connected.")
                else:
                    st.sidebar.warning("⚠️ Ollama client might not be connected. Check if Ollama is running.")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to connect to Ollama: {e}")
                st.session_state.providers['ollama'] = None


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

    # Display status based on selected provider
    active_provider_key = st.session_state.active_provider_key
    client_instance = st.session_state.providers.get(active_provider_key)

    if active_provider_key == 'mistral':
        api_status = "🟢 Connected" if client_instance and getattr(client_instance, 'api_key', None) else "🔴 Not configured"
        st.sidebar.write(f"Mistral AI: {api_status}")
    elif active_provider_key == 'ollama':
        ollama_status = "🟢 Connected" if client_instance and client_instance.list_models() is not None else "🔴 Not connected/configured"
        st.sidebar.write(f"Ollama: {ollama_status}")


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
    
    # Main chat interface
    st.write("Enter your automation objective and I'll help you navigate the web!")

    # Display chat history
    display_chat_history()
    
    # User input
    user_input = st.chat_input("What would you like me to do on the web?")
    
    if user_input:
        add_message("user", user_input)
        
        # Check prerequisites
        active_provider_key = st.session_state.active_provider_key
        active_client = st.session_state.providers.get(active_provider_key)

        if not active_client:
            add_message("assistant", f"The selected AI provider ({st.session_state.selected_provider}) is not configured. Please check the sidebar.", "error")
            st.rerun()
            return
        
        if not st.session_state.browser:
            add_message("assistant", "Please start the browser first using the sidebar controls.", "error")
            st.rerun()
            return # Add this for consistency

        st.session_state.current_objective = user_input
        # New Orchestrator Logic
        st.session_state.orchestrator_active = True
        st.session_state.automation_active = False # Disable old automation loop
        st.session_state.current_task_index = 0 # Reset task index for new objective
        st.session_state.execution_summary = [] # Reset summary

        add_message("assistant", f"Received new objective: {user_input}. Initializing orchestrator and planning steps...")
        
        # Reset todo.md
        todo_manager.reset_todo_file(user_input)
        add_message("assistant", f"📝 `todo.md` reset for objective: {user_input}", "info")

        # Generate Steps
        try:
            active_client = st.session_state.providers.get(st.session_state.active_provider_key)
            if not active_client:
                add_message("assistant", f"AI provider '{st.session_state.selected_provider}' not available. Cannot generate steps.", "error")
                st.session_state.orchestrator_active = False
                st.rerun()
                return

            # TODO: Adjust model names and method calls based on the provider
            # For now, this will likely fail if Ollama is selected and generate_steps_for_todo is not on OllamaClient
            step_generation_model = "pixtral-large-latest" # Example, may need to be dynamic
            add_message("assistant", f"🧠 Generating steps with {st.session_state.selected_provider} (model: {step_generation_model})...", "info")

            if hasattr(active_client, 'generate_steps_for_todo'):
                generated_steps = active_client.generate_steps_for_todo(
                    user_prompt=user_input,
                    model_name=step_generation_model
                )
            else:
                # Fallback or error if the method is not available
                # For Ollama, we might use generate_completion with a specific prompt for step generation
                if st.session_state.active_provider_key == 'ollama':
                    # Example: Use generate_completion for Ollama to attempt step generation
                    ollama_prompt = f"Given the objective: '{user_input}', break it down into a numbered list of actionable steps for web automation. Output only the list."
                    response_text = active_client.generate_completion(prompt=ollama_prompt, model_name="llama2") # Defaulting to llama2 for this
                    if response_text:
                        generated_steps = [step.strip() for step in response_text.splitlines() if step.strip() and step.startswith("- ")]
                        generated_steps = [step[2:] for step in generated_steps] # Remove "- "
                    else:
                        generated_steps = []
                else:
                    generated_steps = []
                    add_message("assistant", f"Method 'generate_steps_for_todo' not available for {st.session_state.selected_provider}.", "error")


            if not generated_steps:
                add_message("assistant", "⚠️ Failed to generate steps or no steps were returned. Please try rephrasing your objective.", "error")
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

                # TODO: Adjust model names based on the provider
                action_decision_model = "mistral-small-latest" # Example, may need to be dynamic

                if hasattr(active_client, 'analyze_and_decide'):
                    response = active_client.analyze_and_decide(
                        image_data, current_task, model_name=action_decision_model, current_context=st.session_state.todo_objective
                    )
                elif st.session_state.active_provider_key == 'ollama':
                    # Fallback for Ollama: use generate_completion
                    # This requires careful prompt engineering for Ollama to return structured action/thinking
                    ollama_action_prompt = f"""Analyze the screenshot (provided as image data) for the task: '{current_task}' with overall objective '{st.session_state.todo_objective}'.
Respond with a JSON object: {{"thinking": "your reasoning", "action": "CLICK(INDEX) or TYPE('text', 'into') or COMPLETE or NAVIGATE_TO('url')"}}"""
                    action_response_text = active_client.generate_completion(
                        prompt=ollama_action_prompt,
                        model_name="llava", # Assuming a multimodal model like llava for image analysis with ollama
                        image_base64=image_data
                    )
                    try:
                        response = json.loads(action_response_text) if action_response_text else {"thinking": "Ollama fallback: No response", "action": ""}
                    except json.JSONDecodeError:
                        response = {"thinking": f"Ollama fallback: Could not parse JSON response: {action_response_text}", "action": ""}
                else:
                    response = {"thinking": f"Method 'analyze_and_decide' not available for {st.session_state.selected_provider}.", "action": ""}
                    add_message("assistant", response["thinking"], "error")


                thinking = response.get('thinking', 'No reasoning provided for action.')
                action_str = response.get('action', '')
                add_message("assistant", f"**Action Model (Mistral-Small-Latest) Reasoning:** {thinking}", "thinking")

                if not action_str:
                    add_message("assistant", "No action could be determined. Trying task again or may need replan.", "error")
                    # Potentially increment a retry counter for the task or stop
                    st.session_state.execution_summary.append({"task": current_task, "action_model_response": response, "status": "No action determined"})
                    st.rerun() # Re-run, might try same task if index not incremented
                    return

                action_executed_successfully = execute_browser_action(action_str)
                st.session_state.execution_summary.append({"task": current_task, "action": action_str, "executed": action_executed_successfully})

                if not action_executed_successfully and action_str.lower() not in ['complete', 'done']:
                     add_message("assistant", f"Action '{action_str}' failed to execute properly. Will re-evaluate.", "error")
                     # Re-run will happen, and the same task will be picked up. analyze_state_vision will assess new state.

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

                # TODO: Adjust model names based on the provider
                vision_model = "pixtral-12b-2409" # Example, may need to be dynamic

                if hasattr(active_client, 'analyze_state_vision'):
                    analysis_result = active_client.analyze_state_vision(
                        image_data_after_action, current_task, st.session_state.todo_objective, model_name=vision_model
                    )
                elif st.session_state.active_provider_key == 'ollama':
                    # Fallback for Ollama: use generate_completion
                    # This requires careful prompt engineering for Ollama to return structured analysis
                    ollama_vision_prompt = f"""Analyze the screenshot (image data provided) after an action for task '{current_task}' and objective '{st.session_state.todo_objective}'.
Respond with a JSON object: {{"error": "error message or null", "task_completed": boolean, "objective_completed": boolean, "summary": "page summary"}}"""
                    vision_response_text = active_client.generate_completion(
                        prompt=ollama_vision_prompt,
                        model_name="llava", # Assuming llava for ollama vision
                        image_base64=image_data_after_action
                    )
                    try:
                        analysis_result = json.loads(vision_response_text) if vision_response_text else {"summary": "Ollama fallback: No vision response", "task_completed": False, "objective_completed": False, "error": None}
                        # Ensure boolean types are correct after loading from JSON
                        analysis_result["task_completed"] = str(analysis_result.get("task_completed", "false")).lower() == "true"
                        analysis_result["objective_completed"] = str(analysis_result.get("objective_completed", "false")).lower() == "true"
                    except json.JSONDecodeError:
                        analysis_result = {"summary": f"Ollama fallback: Could not parse JSON vision response: {vision_response_text}", "task_completed": False, "objective_completed": False, "error": "JSON Parse Error"}
                else:
                    analysis_result = {"summary": f"Method 'analyze_state_vision' not available for {st.session_state.selected_provider}.", "task_completed": False, "objective_completed": False, "error": "Method not available"}
                    add_message("assistant", analysis_result["summary"], "error")

                analysis_summary = analysis_result.get('summary', 'No analysis summary provided.')
                add_message("assistant", f"**Vision Model (Pixtral-12B-2409) Analysis:** {analysis_summary}", "info")
                st.session_state.execution_summary.append({"task": current_task, "vision_analysis": analysis_result})

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

            st.rerun()

        else: # All tasks processed (task_idx >= len(tasks))
            add_message("assistant", "✅ All tasks from todo.md have been processed. Performing final verification.", "info")
            # Perform a final vision analysis
            final_annotated_image_path = take_screenshot_and_analyze()
            if final_annotated_image_path:
                try:
                    with open(final_annotated_image_path, 'rb') as img_file:
                        final_image_data = base64.b64encode(img_file.read()).decode('utf-8')

                    # TODO: Adjust model name
                    vision_model_final = "pixtral-12b-2409" # Example
                    if hasattr(active_client, 'analyze_state_vision'):
                        final_analysis = active_client.analyze_state_vision(
                            final_image_data, "Final objective verification", st.session_state.todo_objective, model_name=vision_model_final
                        )
                    elif st.session_state.active_provider_key == 'ollama':
                         ollama_final_vision_prompt = f"""Final verification of objective '{st.session_state.todo_objective}' based on screenshot.
Respond with JSON: {{"error": "error or null", "task_completed": boolean, "objective_completed": boolean, "summary": "page summary"}}"""
                         final_vision_response_text = active_client.generate_completion(prompt=ollama_final_vision_prompt, model_name="llava", image_base64=final_image_data)
                         try:
                             final_analysis = json.loads(final_vision_response_text) if final_vision_response_text else {"summary": "Ollama fallback: No final vision response", "objective_completed": False}
                             final_analysis["objective_completed"] = str(final_analysis.get("objective_completed", "false")).lower() == "true"
                         except json.JSONDecodeError:
                            final_analysis = {"summary": f"Ollama fallback: Could not parse JSON final vision response: {final_vision_response_text}", "objective_completed": False}
                    else:
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

    # Auto-continue legacy automation if active (and orchestrator is not) - This part can be removed if legacy is fully deprecated.
    if st.session_state.get('automation_active') and not st.session_state.get('orchestrator_active'):
        add_message("assistant", "Legacy automation loop triggered (should be deprecated).", "info")
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
