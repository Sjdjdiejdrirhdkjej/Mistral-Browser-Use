import os
from e2b_code_interpreter import Sandbox, Execution

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
            self.sandbox = Sandbox(api_key=self.api_key)
            self._is_session_active = True
            print("E2B session started.")
            self._ensure_tools()
        except Exception as e:
            self._is_session_active = False
            print(f"Failed to start E2B session: {e}")
            raise

    def _ensure_tools(self):
        if not self.sandbox:
            print("Sandbox not initialized. Cannot install tools.")
            return
        tools = ["firefox", "xdotool", "scrot"]
        for tool in tools:
            check_process = self.sandbox.run_code(f"import shutil; print(shutil.which('{tool}'))")
            stdout_result = "".join(m.line for m in check_process.results if hasattr(m, 'line'))
            if stdout_result.strip() == "None" or not stdout_result.strip():
                print(f"{tool} not found, attempting to install...")
                try:
                    self.run_shell_command(f"sudo apt-get update && sudo apt-get install -y {tool}")
                    print(f"{tool} installed successfully.")
                except Exception as e_install:
                    print(f"Failed to install {tool}. Error: {e_install}")
            else:
                print(f"{tool} is already installed at: {stdout_result.strip()}")

    def close_session(self):
        if not self._is_session_active or not self.sandbox:
            print("Session not active or sandbox not initialized.")
            return
        try:
            self.sandbox.close()
            self._is_session_active = False
            print("E2B session closed.")
        except Exception as e:
            print(f"Error closing E2B session: {e}")

    def run_code_in_sandbox(self, code: str, timeout: int = 60) -> Execution:
        if not self._is_session_active or not self.sandbox:
            raise Exception("E2B session not active. Cannot run code.")
        print(f"Running code in sandbox: {code}")
        execution = self.sandbox.run_code(code, timeout=timeout*1000)
        if execution.error:
            print(f"Error during code execution: {execution.error.name} - {execution.error.value}")
            print(f"Traceback: {''.join(execution.error.traceback)}")
        return execution

    def run_shell_command(self, command: str, timeout: int = 60):
        if not self.sandbox or not self._is_session_active:
            raise Exception("Sandbox not active.")
        print(f"Running shell command: {command}")
        proc = self.sandbox.process.start(command, timeout=timeout*1000)
        proc.wait()
        output = "".join([msg.line for msg in proc.output_messages])
        error_output = "".join([msg.line for msg in proc.error_messages])
        print(f"Shell command stdout: {output}")
        if proc.exit_code != 0:
            print(f"Shell command stderr: {error_output}")
            raise Exception(f"Shell command failed with exit code {proc.exit_code}: {error_output}")
        return output, error_output

    def navigate_to(self, url: str):
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        command = f"setsid firefox '{url}' > /dev/null 2>&1 &"
        print(f"Attempting to navigate to {url} using command: {command}")
        try:
            proc = self.sandbox.process.start(command, timeout=10*1000)
            print(f"Successfully initiated navigation to {url} (PID: {proc.pid if proc else 'unknown'}). Check E2B desktop.")
        except Exception as e:
            print(f"Failed to navigate to {url}: {e}")

    def take_screenshot(self, output_filepath: str = "screenshot.png") -> str | None:
        if not self.sandbox or not self._is_session_active:
            print("Error: Sandbox not active. Cannot take screenshot.") # Added print for clarity
            raise Exception("Sandbox not active.") # Keep exception for app.py to catch if needed

        sandbox_image_path = f"/tmp/{output_filepath}"
        # Ensure scrot is installed; _ensure_tools should have run, but double check or handle failure.
        # Forcing display for scrot, though E2B environment should handle this.
        command = f"export DISPLAY=:0 && scrot -o '{sandbox_image_path}'"

        scrot_stdout = ""
        scrot_stderr = ""

        try:
            print(f"Attempting to take screenshot using command: {command}")
            # self.run_shell_command will raise an exception if scrot fails (non-zero exit code)
            # and will print stdout/stderr in that case.
            scrot_stdout, scrot_stderr = self.run_shell_command(command) # run_shell_command now returns (output, error_output)
            print(f"Screenshot command executed. STDOUT: {scrot_stdout}, STDERR: {scrot_stderr}")
            # Even if exit code is 0, scrot might print to stderr (e.g., warnings)

        except Exception as e_scrot:
            print(f"Error during scrot command execution: {e_scrot}")
            # scrot_stdout and scrot_stderr might already be printed by run_shell_command if it raised an exception
            # due to non-zero exit. If e_scrot is from a different phase (e.g. Popen issue), they might be empty.
            # Ensure they are available if run_shell_command was modified to populate them even on Popen error.
            # The current run_shell_command only populates them well if proc.wait() completes.
            return None # Exit early if scrot command failed

        try:
            print(f"Attempting to download {sandbox_image_path} from sandbox...")
            file_content_bytes = self.sandbox.download_file(sandbox_image_path)

            local_image_path = output_filepath
            with open(local_image_path, "wb") as f:
                f.write(file_content_bytes)
            print(f"Screenshot downloaded and saved to local path: {local_image_path}")
            return local_image_path

        except Exception as e_download:
            print(f"Error during screenshot download from sandbox: {e_download}")
            print(f"Scrot command STDOUT was: {scrot_stdout}") # Log scrot output for context
            print(f"Scrot command STDERR was: {scrot_stderr}")
            return None

        # Fallback, though should be covered by try/excepts
        return None

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
        e2b_auto = E2BDesktopAutomation()
        e2b_auto.start_session()
        if e2b_auto._is_session_active and e2b_auto.sandbox:
            print("\nRunning 'ls -la /' in sandbox:")
            ls_output, ls_error = e2b_auto.run_shell_command("ls -la /")
            print("\nAttempting to take a screenshot:")
            screenshot_file = e2b_auto.take_screenshot("test_screenshot.png")
            if screenshot_file:
                print(f"Screenshot saved to: {screenshot_file}")
            else:
                print("Failed to get screenshot.")
        else:
            print("Session could not be started or sandbox not available.")
    except Exception as e:
        print(f"An error occurred during the test: {e}")
    finally:
        if e2b_auto and e2b_auto._is_session_active:
            print("\nClosing E2B session...")
            e2b_auto.close_session()
        print("Test script finished.")
