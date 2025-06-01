import os
from e2b_desktop import Sandbox # Changed
from PIL import Image # Added
import io # Added
# Execution type hint removed from original e2b_code_interpreter import

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
            self.sandbox = Sandbox(api_key=self.api_key) # type: ignore Sandbox from e2b_desktop might have different type expectations
            self._is_session_active = True
            print("E2B session started.")
            self._ensure_tools()
        except Exception as e:
            self._is_session_active = False
            print(f"Failed to start E2B session: {e}")
            raise

    def _ensure_tools(self):
        """Ensures necessary tools like firefox, xdotool, scrot are installed."""
        if not self.sandbox:
            print("Sandbox not initialized. Cannot install tools.")
            return

        tools = ["firefox", "xdotool", "scrot"] # scrot is no longer needed if using self.sandbox.screenshot()
        # Consider removing scrot or making its check/install conditional if other methods still use it.
        # For now, keeping it as per previous structure, but it's unused by the new take_screenshot.

        tools_to_check = ["firefox", "xdotool"] # Scrot check removed
        if not self.uses_native_screenshot(): # Only check for scrot if not using native screenshot
            tools_to_check.append("scrot")


        for tool in tools_to_check:
            # Assuming e2b_desktop.Sandbox has a compatible run_code or equivalent.
            # This part might need adjustment based on e2b_desktop.Sandbox capabilities.
            try:
                # The run_code method might not exist or work the same way.
                # This is a placeholder for how one might check for tools.
                # For now, we'll assume it might fail gracefully or be adapted later.
                print(f"Checking for tool: {tool} (Note: run_code compatibility with e2b_desktop.Sandbox TBD)")
                check_process = self.sandbox.run_code(f"import shutil; print(shutil.which('{tool}'))") # type: ignore
                stdout_result = "".join(m.line for m in check_process.results if hasattr(m, 'line')) # type: ignore
                if stdout_result.strip() == "None" or not stdout_result.strip():
                    print(f"{tool} not found, attempting to install...")
                    self.run_shell_command(f"sudo apt-get update && sudo apt-get install -y {tool}")
                    print(f"{tool} installed successfully.")
                else:
                    print(f"{tool} is already installed at: {stdout_result.strip()}")
            except Exception as e_tool_check:
                print(f"Could not check/install tool {tool}. It might be unavailable or run_code is incompatible: {e_tool_check}")


    def close_session(self):
        if not self._is_session_active or not self.sandbox:
            print("Session not active or sandbox not initialized.")
            return
        try:
            self.sandbox.close() # type: ignore
            self._is_session_active = False
            print("E2B session closed.")
        except Exception as e:
            print(f"Error closing E2B session: {e}")

    def run_code_in_sandbox(self, code: str, timeout: int = 60) -> any: # Return type changed
        if not self._is_session_active or not self.sandbox:
            raise Exception("E2B session not active. Cannot run code.")
        print(f"Running code in sandbox: {code} (Note: run_code compatibility with e2b_desktop.Sandbox TBD)")
        # Assuming e2b_desktop.Sandbox has a compatible run_code method.
        execution = self.sandbox.run_code(code, timeout=timeout*1000) # type: ignore
        if hasattr(execution, 'error') and execution.error: # Check if error attribute exists
            print(f"Error during code execution: {execution.error.name} - {execution.error.value}") # type: ignore
            print(f"Traceback: {''.join(execution.error.traceback)}") # type: ignore
        return execution

    def run_shell_command(self, command: str, timeout: int = 60):
        if not self.sandbox or not self._is_session_active:
            raise Exception("Sandbox not active.")
        print(f"Running shell command: {command} (Note: process.start compatibility with e2b_desktop.Sandbox TBD)")
        # Assuming e2b_desktop.Sandbox has a compatible process.start method.
        proc = self.sandbox.process.start(command, timeout=timeout*1000) # type: ignore
        proc.wait()
        output = "".join([msg.line for msg in proc.output_messages]) # type: ignore
        error_output = "".join([msg.line for msg in proc.error_messages]) # type: ignore
        print(f"Shell command stdout: {output}")
        if proc.exit_code != 0:
            print(f"Shell command stderr: {error_output}")
            raise Exception(f"Shell command failed with exit code {proc.exit_code}: {error_output}")
        return output, error_output

    @staticmethod
    def uses_native_screenshot() -> bool:
        # Helper to check if we are using the new native screenshot method
        return True # Since we just rewrote take_screenshot to use it

    def take_screenshot(self, output_filepath: str = "e2b_screenshot.png") -> str | None:
        if not self.sandbox or not self._is_session_active:
            print("Error: Sandbox not active. Cannot take screenshot.")
            return None

        print("Attempting to take screenshot using e2b_desktop.Sandbox.screenshot()...")
        try:
            image_bytes = self.sandbox.screenshot() # This is the new call # type: ignore

            if not image_bytes:
                print("Error: sandbox.screenshot() returned empty bytes.")
                return None

            print(f"Screenshot captured successfully, {len(image_bytes)} bytes received.")

            image = Image.open(io.BytesIO(image_bytes))

            local_image_path = output_filepath
            # Ensure directory exists if output_filepath contains a path
            os.makedirs(os.path.dirname(local_image_path) or '.', exist_ok=True)
            image.save(local_image_path)

            print(f"Screenshot saved locally to: {local_image_path}")
            return local_image_path

        except Exception as e:
            print(f"Error during e2b_desktop.screenshot() or image processing: {e}")
            import traceback # Local import for traceback
            print(traceback.format_exc())
            return None

    def navigate_to(self, url: str):
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        command = f"setsid firefox '{url}' > /dev/null 2>&1 &"
        print(f"Attempting to navigate to {url} using command: {command}")
        try:
            proc = self.sandbox.process.start(command, timeout=10*1000) # type: ignore
            print(f"Successfully initiated navigation to {url} (PID: {proc.pid if proc else 'unknown'}). Check E2B desktop.")
        except Exception as e:
            print(f"Failed to navigate to {url}: {e}")

    def click_at_coords(self, x: int, y: int):
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        command = f"xdotool mousemove {x} {y} click 1"
        print(f"Attempting to click at ({x},{y}) using command: {command}")
        try:
            self.run_shell_command(command)
            print(f"Successfully clicked at ({x},{y}).")
        except Exception as e:
            print(f"Failed to click at ({x},{y}): {e}")

    def type_text(self, text_to_type: str):
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        command = f"xdotool type --delay 100 '{text_to_type}'"
        print(f"Attempting to type text: '{text_to_type}' using command: {command}")
        try:
            self.run_shell_command(command)
            print(f"Successfully typed text.")
        except Exception as e:
            print(f"Failed to type text: {e}")

    def press_key(self, key_name: str):
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        command = f"xdotool key '{key_name}'"
        print(f"Attempting to press key: '{key_name}' using command: {command}")
        try:
            self.run_shell_command(command)
            print(f"Successfully pressed key '{key_name}'.")
        except Exception as e:
            print(f"Failed to press key '{key_name}': {e}")

if __name__ == '__main__':
    print("Starting E2BDesktopAutomation Test Script...")
    e2b_auto = None
    try:
        # Ensure E2B_API_KEY is set in your environment for this test to run.
        if not os.getenv("E2B_API_KEY"):
            print("CRITICAL: E2B_API_KEY environment variable not set. This test script requires it.")
        else:
            e2b_auto = E2BDesktopAutomation()
            e2b_auto.start_session()
            if e2b_auto._is_session_active and e2b_auto.sandbox:
                print("\nAttempting to take a screenshot (native):")
                screenshot_file = e2b_auto.take_screenshot("test_native_screenshot.png")
                if screenshot_file:
                    print(f"Native screenshot saved to: {screenshot_file}")
                else:
                    print("Failed to get native screenshot.")

                # Example: Run a simple shell command (ls)
                print("\nRunning 'ls -la /tmp' in sandbox:")
                ls_output, ls_error = e2b_auto.run_shell_command("ls -la /tmp")
                # print(f"Output:\n{ls_output}")

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
