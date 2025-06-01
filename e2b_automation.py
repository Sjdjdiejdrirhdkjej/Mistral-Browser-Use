import os
from e2b_desktop import Sandbox
from PIL import Image
import io
import time

class E2BDesktopAutomation:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        if not self.api_key:
            raise ValueError("E2B_API_KEY not found in environment variables or provided.")

        self.sandbox: Sandbox | None = None
        self._is_session_active = False

    def start_session(self):
        if self._is_session_active and self.sandbox:
            print("Session already active.")
            return
        try:
            self.sandbox = Sandbox(api_key=self.api_key) # type: ignore
            # Xvfb manual startup removed

            self._is_session_active = True
            print("E2B session started (assuming ambient display).")
            self._ensure_tools()

        except Exception as e:
            self._is_session_active = False
            # Removed Xvfb process kill from this cleanup as it's no longer managed here
            if self.sandbox:
                 try:
                    self.sandbox.close() # type: ignore
                 except Exception as e_close:
                    print(f"Failed to close sandbox during error cleanup: {e_close}")
            self.sandbox = None
            # self.xvfb_process = None # Attribute removed
            print(f"Failed to start E2B session fully: {e}")
            raise

    def _ensure_tools(self):
        if not self.sandbox:
            print("Sandbox not initialized. Cannot install tools.")
            return

        apt_tools = ["xvfb", "python3-pip", "firefox-esr"]

        for tool in apt_tools:
            try:
                print(f"Checking for APT tool: {tool}")
                tool_path_stdout, _ = self.run_shell_command(f"which {tool}", use_display=False)
                if tool_path_stdout.strip():
                    print(f"{tool} is already installed at: {tool_path_stdout.strip()}")
                else:
                    print(f"{tool} not found by 'which', attempting install...")
                    self.run_shell_command(f"sudo apt-get update && sudo apt-get install -y {tool}", use_display=False)
                    print(f"{tool} installation attempted.")
            except Exception as e_apt_check:
                print(f"Attempting to install APT tool: {tool} (either 'which' failed or tool not found). Error context: {e_apt_check}")
                try:
                    self.run_shell_command(f"sudo apt-get update && sudo apt-get install -y {tool}", use_display=False)
                    print(f"APT tool {tool} installed successfully after initial check/failure.")
                except Exception as e_apt_install:
                    print(f"Failed to install APT tool {tool}. Error: {e_apt_install}")

        pip3_available = False
        try:
            pip3_path_stdout, _ = self.run_shell_command("which pip3", use_display=False)
            if pip3_path_stdout.strip():
                pip3_available = True
                print(f"pip3 is available at: {pip3_path_stdout.strip()}")
        except Exception:
            print("pip3 not found via 'which' after apt installation attempt.")

        if pip3_available:
            print("Attempting to install pyautogui using pip3...")
            pip_install_command = "pip3 install pyautogui"
            try:
                install_pyautogui_stdout, install_pyautogui_stderr = self.run_shell_command(pip_install_command, use_display=False)
                print(f"pyautogui installation STDOUT: {install_pyautogui_stdout}")
                if install_pyautogui_stderr and install_pyautogui_stderr.strip():
                    print(f"pyautogui installation STDERR: {install_pyautogui_stderr.strip()}")
                print("pyautogui installation command executed.")
            except Exception as e_pip:
                print(f"Failed to install pyautogui using pip3: {e_pip}")
        else:
            print("pip3 not found after apt checks. Cannot install pyautogui.")

    def close_session(self):
        if not self._is_session_active or not self.sandbox:
            print("Session not active or sandbox not initialized.")
            return
        try:
            # Removed Xvfb process kill as it's no longer managed here

            self.sandbox.close() # type: ignore
            self._is_session_active = False
            print("E2B session closed.")
        except Exception as e:
            print(f"Error closing E2B session: {e}")

    def run_code_in_sandbox(self, code: str, timeout: int = 60, use_display: bool = False) -> any:
        if not self._is_session_active or not self.sandbox:
            raise Exception("E2B session not active. Cannot run code.")

        env_vars = {} # Initialize empty
        if use_display:
            # We assume E2B's environment or the sandbox itself has DISPLAY correctly set.
            # If specific DISPLAY is needed and known, it could be os.getenv("DISPLAY")
            # but for now, let E2B manage it unless issues arise.
            print(f"Running code in sandbox (use_display=True, relying on ambient DISPLAY) for script: <see below>")
        else:
            print(f"Running code in sandbox (use_display=False) for script: <see below>")
        print(code)
        # The `env_vars` passed to `self.sandbox.run_code` will be empty unless other specific vars are needed.

        execution = self.sandbox.run_code(code, timeout=timeout*1000, env_vars=env_vars) # type: ignore

        # Process results for stdout/stderr from the new Execution structure
        stdout = "".join(m.line for m in execution.results if hasattr(m, 'line')) # type: ignore
        stderr = execution.error.value if hasattr(execution, 'error') and execution.error else "" # type: ignore

        if stdout:
            print(f"Script stdout: {stdout}")
        if stderr: # This will print if execution.error is present
             print(f"Script stderr (from error): {stderr}")
        if hasattr(execution, 'error') and execution.error:
            print(f"Error during code execution: {execution.error.name} - {execution.error.value}") # type: ignore
            print(f"Traceback: {''.join(execution.error.traceback)}") # type: ignore

        # Make the return more informative, similar to what app.py might expect from old run_code
        # This is a placeholder; the actual structure of `execution` from e2b_desktop needs to be known.
        # For now, returning the whole object.
        return execution


    def run_shell_command(self, command: str, timeout: int = 60, use_display: bool = False):
        if not self.sandbox or not self._is_session_active:
            raise Exception("Sandbox not active.")

        full_command = command
        if use_display:
            # Rely on the sandbox's ambient DISPLAY variable.
            print(f"Running shell command (use_display=True, relying on ambient DISPLAY): {full_command}")
        else:
            print(f"Running shell command (use_display=False): {full_command}")

        proc = self.sandbox.process.start(full_command, timeout=timeout*1000) # type: ignore
        proc.wait()
        output = "".join([msg.line for msg in proc.output_messages]) # type: ignore
        error_output = "".join([msg.line for msg in proc.error_messages]) # type: ignore
        print(f"Shell command stdout: {output}")
        if proc.exit_code != 0:
            print(f"Shell command stderr: {error_output}")
            raise Exception(f"Shell command failed with exit code {proc.exit_code}: {error_output}")
        return output, error_output

    def take_screenshot(self, output_filepath: str = "e2b_screenshot.png") -> str | None:
        if not self.sandbox or not self._is_session_active:
            print("Error: Sandbox not active. Cannot take screenshot.")
            return None
        # Removed self.xvfb_process check
        # Removed self.display check

        print("Attempting to take screenshot using e2b_desktop.Sandbox.screenshot()...")
        try:
            image_bytes = self.sandbox.screenshot() # type: ignore

            if not image_bytes:
                print("Error: sandbox.screenshot() returned empty bytes.")
                return None

            print(f"Screenshot captured successfully, {len(image_bytes)} bytes received.")
            image = Image.open(io.BytesIO(image_bytes))
            local_image_path = output_filepath
            os.makedirs(os.path.dirname(local_image_path) or '.', exist_ok=True)
            image.save(local_image_path)
            print(f"Screenshot saved locally to: {local_image_path}")
            return local_image_path
        except Exception as e:
            print(f"Error during e2b_desktop.screenshot() or image processing: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def navigate_to(self, url: str): # Kept as is, uses firefox
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        # Removed self.display check for Xvfb
        command = f"firefox '{url}'" # Rely on ambient DISPLAY
        print(f"Attempting to navigate to {url} using command (relying on ambient DISPLAY): {command}")
        try:
            self.run_shell_command(command, timeout=20, use_display=True) # Increased timeout slightly
            print(f"Firefox navigation command for {url} executed. Check E2B desktop.")
        except Exception as e:
            print(f"Failed to execute Firefox for navigation to {url}: {e}")

    def click_at_coords(self, x: int, y: int):
        if not self._is_session_active or not self.sandbox: # type: ignore
            raise Exception("E2B session not active.")
        # Removed self.display check for Xvfb

        py_script = f"""
import pyautogui
import os
try:
    print(f"PyAutoGUI: Executing click at ({x}, {y}) with DISPLAY={os.environ.get('DISPLAY')}")
    pyautogui.moveTo({x}, {y}, duration=0.1)
    pyautogui.click({x}, {y})
    print(f"PyAutoGUI: Successfully clicked at ({x}, {y})")
except Exception as e_click:
    print(f"PyAutoGUI: Click failed: {{e_click}}")
    raise
"""
        print(f"Attempting to click at ({x},{y}) using PyAutoGUI...")
        try:
            execution_result = self.run_code_in_sandbox(py_script, use_display=True)
            if execution_result and hasattr(execution_result, 'error') and execution_result.error:
                print(f"PyAutoGUI click script execution failed (reported by run_code_in_sandbox).")
            # Further stdout/stderr from script itself is now handled inside run_code_in_sandbox
        except Exception as e:
            print(f"Failed to execute PyAutoGUI click script: {e}")

    def type_text(self, text_to_type: str):
        if not self._is_session_active or not self.sandbox: # type: ignore
            raise Exception("E2B session not active.")
        # Removed self.display check for Xvfb

        escaped_text = text_to_type.replace("'", "\\'")

        py_script = f"""
import pyautogui
import os
try:
    print(f"PyAutoGUI: Executing type_text with DISPLAY={os.environ.get('DISPLAY')}")
    pyautogui.write('{escaped_text}', interval=0.02)
    print(f"PyAutoGUI: Successfully typed text.")
except Exception as e_type:
    print(f"PyAutoGUI: Write failed: {{e_type}}")
    raise
"""
        print(f"Attempting to type text: '{text_to_type}' using PyAutoGUI...")
        try:
            execution_result = self.run_code_in_sandbox(py_script, use_display=True)
            if execution_result and hasattr(execution_result, 'error') and execution_result.error:
                print(f"PyAutoGUI type script execution failed (reported by run_code_in_sandbox).")
        except Exception as e:
            print(f"Failed to execute PyAutoGUI type script: {e}")

    def press_key(self, key_name: str):
        if not self._is_session_active or not self.sandbox: # type: ignore
            raise Exception("E2B session not active.")
        # Removed self.display check for Xvfb

        key_map = {
            "RETURN": "enter", "ENTER": "enter", "ESC": "escape",
            "ESCAPE": "escape", "TAB": "tab",
        }
        pyautogui_key = key_map.get(key_name.upper(), key_name.lower())

        py_script = f"""
import pyautogui
import os
try:
    print(f"PyAutoGUI: Executing press_key '{pyautogui_key}' with DISPLAY={os.environ.get('DISPLAY')}")
    pyautogui.press('{pyautogui_key}')
    print(f"PyAutoGUI: Successfully pressed key '{pyautogui_key}'.")
except Exception as e_press:
    print(f"PyAutoGUI: Press failed for key '{pyautogui_key}': {{e_press}}")
    raise
"""
        print(f"Attempting to press key: '{key_name}' (as '{pyautogui_key}') using PyAutoGUI...")
        try:
            execution_result = self.run_code_in_sandbox(py_script, use_display=True)
            if execution_result and hasattr(execution_result, 'error') and execution_result.error:
                print(f"PyAutoGUI press key script execution failed (reported by run_code_in_sandbox).")
        except Exception as e:
            print(f"Failed to execute PyAutoGUI press key script: {e}")

if __name__ == '__main__':
    print("Starting E2BDesktopAutomation Test Script...")
    e2b_auto = None
    try:
        if not os.getenv("E2B_API_KEY"):
            print("CRITICAL: E2B_API_KEY environment variable not set. This test script requires it.")
        else:
            e2b_auto = E2BDesktopAutomation()
            e2b_auto.start_session()
            if e2b_auto._is_session_active and e2b_auto.sandbox:
                # print(f"Session started with display {e2b_auto.display} and Xvfb process {e2b_auto.xvfb_process}") # display and xvfb_process attributes removed
                print(f"Session started (relying on ambient display).")

                print("\nAttempting to take a screenshot (native):")
                screenshot_file = e2b_auto.take_screenshot("test_native_screenshot.png")
                if screenshot_file:
                    print(f"Native screenshot saved to: {screenshot_file}")
                else:
                    print("Failed to get native screenshot.")

                print("\nTesting PyAutoGUI click (e.g., at 100,100):")
                e2b_auto.click_at_coords(100, 100)
                time.sleep(0.5) # Pause after action

                print("\nTesting PyAutoGUI type_text (e.g., 'Hello E2B!'):")
                e2b_auto.type_text("Hello E2B!")
                time.sleep(0.5)

                print("\nTesting PyAutoGUI press_key (e.g., 'Enter'):")
                e2b_auto.press_key("Enter")
                time.sleep(0.5)

                # print("\nAttempting to navigate to a test page with Firefox:")
                # e2b_auto.navigate_to("https://example.com")
                # time.sleep(5) # Give time for firefox to open
                # screenshot_after_nav = e2b_auto.take_screenshot("test_firefox_nav.png")
                # if screenshot_after_nav:
                #     print(f"Screenshot after Firefox navigation saved to: {screenshot_after_nav}")
                # else:
                #     print("Failed to get screenshot after Firefox navigation.")

            else:
                print("Session could not be started or sandbox not available.")
    except Exception as e:
        print(f"An error occurred during the test: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        if e2b_auto and e2b_auto._is_session_active:
            print("\nClosing E2B session...")
            e2b_auto.close_session()
        print("Test script finished.")
