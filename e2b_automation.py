import os
from e2b_code_interpreter import Sandbox, Execution

class E2BDesktopAutomation:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        if not self.api_key:
            raise ValueError("E2B_API_KEY not found in environment variables or provided.")

        # Initialize sandbox to None. It will be created in start_session.
        self.sandbox: Sandbox | None = None
        self._is_session_active = False

    def start_session(self):
        """Starts the E2B sandbox session."""
        if self._is_session_active and self.sandbox:
            print("Session already active.")
            return

        try:
            # The Sandbox constructor might take the api_key directly or expect it to be in env.
            # Checking docs: The SDK seems to primarily rely on the E2B_API_KEY env var.
            # If direct API key passing is supported by Sandbox, it would be:
            # self.sandbox = Sandbox(api_key=self.api_key)
            # For now, assume env var is picked up automatically by the Sandbox class.
            self.sandbox = Sandbox(api_key=self.api_key) # Explicitly pass the resolved API key

            # The Sandbox is typically used with a context manager (with Sandbox() as sandbox:).
            # To manage it manually, we might need to call internal open/close methods if available,
            # or handle its lifecycle carefully. The provided examples use `with`.
            # Let's assume for now that creating an instance makes it ready,
            # and we'll manage its closing in close_session.
            # According to SDK, Sandbox() starts it.

            self._is_session_active = True
            print("E2B session started.")
            # Install necessary tools if not part of the default E2B environment.
            # This is a good place to ensure firefox, xdotool, scrot are present.
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

        tools = ["firefox", "xdotool", "scrot"]
        for tool in tools:
            # Check if tool exists (simple check, might need refinement)
            # Using `which` command to check.
            check_process = self.sandbox.run_code(f"import shutil; print(shutil.which('{tool}'))")
            # run_python returns an Execution object, not a ProcessMessage array
            # Access stdout from the Execution object
            stdout_result = "".join(m.line for m in check_process.results if hasattr(m, 'line'))


            if stdout_result.strip() == "None" or not stdout_result.strip(): # More robust check might be needed
                print(f"{tool} not found, attempting to install...")
                # Attempt to install using apt-get. This assumes a Debian-based E2B environment.
                # Using run_shell_command for apt-get might be more direct
                try:
                    self.run_shell_command(f"sudo apt-get update && sudo apt-get install -y {tool}")
                    print(f"{tool} installed successfully.")
                except Exception as e_install:
                    print(f"Failed to install {tool}. Error: {e_install}")
                    # Decide if this is a critical failure
            else:
                print(f"{tool} is already installed at: {stdout_result.strip()}")


    def close_session(self):
        """Closes the E2B sandbox session."""
        if not self._is_session_active or not self.sandbox:
            print("Session not active or sandbox not initialized.")
            return
        try:
            self.sandbox.close() # This is the correct method to close the sandbox
            self._is_session_active = False
            print("E2B session closed.")
        except Exception as e:
            print(f"Error closing E2B session: {e}")

    def run_code_in_sandbox(self, code: str, timeout: int = 60) -> Execution:
        """Runs Python code in the sandbox and returns the execution result."""
        if not self._is_session_active or not self.sandbox:
            raise Exception("E2B session not active. Cannot run code.")

        print(f"Running code in sandbox: {code}")
        # The `run_python` method is suitable for Python code.
        # For shell commands (like running firefox, xdotool), `run_javascript` with Node.js `child_process`
        # or a specific shell execution method if available would be better.
        # `e2b_code_interpreter.Sandbox` has `process.start()` for general processes.
        # For simplicity in this step, let's assume Python can trigger these or we'll refine.
        # The example `sandbox.run_code("x=1")` seems to be for Python.
        # Let's stick to `run_python` for Python code execution as per its name.
        execution = self.sandbox.run_code(code, timeout=timeout*1000) # timeout in ms

        if execution.error:
            print(f"Error during code execution: {execution.error.name} - {execution.error.value}")
            print(f"Traceback: {''.join(execution.error.traceback)}")

        return execution

    def run_shell_command(self, command: str, timeout: int = 60):
        """Runs a shell command in the sandbox."""
        if not self.sandbox or not self._is_session_active:
            raise Exception("Sandbox not active.")

        print(f"Running shell command: {command}")
        proc = self.sandbox.process.start(command, timeout=timeout*1000) # timeout in ms
        proc.wait() # Wait for the process to complete

        output = "".join([msg.line for msg in proc.output_messages])
        error_output = "".join([msg.line for msg in proc.error_messages])

        print(f"Shell command stdout: {output}")
        if proc.exit_code != 0:
            print(f"Shell command stderr: {error_output}")
            raise Exception(f"Shell command failed with exit code {proc.exit_code}: {error_output}")
        return output, error_output


    def navigate_to(self, url: str):
        """Navigates to a URL in the E2B environment's browser (assumes Firefox)."""
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        # This assumes 'firefox' is installed and in PATH within the sandbox.
        # Also assumes it can run in the background or is handled appropriately.
        # Using `setsid` to detach the process
        command = f"setsid firefox '{url}' > /dev/null 2>&1 &"
        print(f"Attempting to navigate to {url} using command: {command}")
        try:
            # For commands that launch GUI apps and run in background,
            # we might not want to wait for completion in the same way as other shell commands.
            # Process.start might be better if we don't need to wait for exit code here.
            proc = self.sandbox.process.start(command, timeout=10*1000) # Short timeout
            # We don't call proc.wait() here as firefox will run in the background.
            print(f"Successfully initiated navigation to {url} (PID: {proc.pid if proc else 'unknown'}). Check E2B desktop.")
        except Exception as e:
            print(f"Failed to navigate to {url}: {e}")
            # May need to check if firefox is running, etc.

    def take_screenshot(self, output_filepath: str = "screenshot.png") -> str | None:
        """
        Takes a screenshot of the E2B desktop.
        Assumes 'scrot' is installed in the sandbox.
        Saves it in the sandbox, then downloads it.
        Returns the path to the downloaded local screenshot, or None on failure.
        """
        if not self.sandbox or not self._is_session_active:
            raise Exception("Sandbox not active.")

        sandbox_image_path = f"/tmp/{output_filepath}" # Save to /tmp in sandbox
        command = f"scrot -o '{sandbox_image_path}'" # -o to overwrite if exists

        try:
            print("Attempting to take screenshot using scrot...")
            self.run_shell_command(command)
            print(f"Screenshot supposedly saved to {sandbox_image_path} in sandbox.")

            # Download the file
            print(f"Attempting to download {sandbox_image_path}...")
            file_content_bytes = self.sandbox.download_file(sandbox_image_path)

            # Save it locally
            local_image_path = output_filepath
            with open(local_image_path, "wb") as f:
                f.write(file_content_bytes)
            print(f"Screenshot downloaded and saved to local path: {local_image_path}")
            return local_image_path
        except Exception as e:
            print(f"Failed to take or download screenshot: {e}")
            return None

    # Placeholder for more complex GUI interactions
    def click_at_coords(self, x: int, y: int):
        """Clicks at specified coordinates using xdotool."""
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
        """Types the given text using xdotool."""
        if not self._is_session_active:
            raise Exception("E2B session not active.")
        # Ensure text is properly escaped for shell command if necessary
        command = f"xdotool type --delay 100 '{text_to_type}'" # Added delay for reliability
        print(f"Attempting to type text: '{text_to_type}' using command: {command}")
        try:
            self.run_shell_command(command)
            print(f"Successfully typed text.")
        except Exception as e:
            print(f"Failed to type text: {e}")

    def press_key(self, key_name: str):
        """Presses a key using xdotool (e.g., 'Return', 'Escape', 'Tab')."""
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
    # This is a basic test script.
    # Ensure E2B_API_KEY is set in your environment.
    print("Starting E2BDesktopAutomation Test Script...")
    e2b_auto = None # Define e2b_auto outside try for finally block
    try:
        e2b_auto = E2BDesktopAutomation()
        e2b_auto.start_session()

        if e2b_auto._is_session_active and e2b_auto.sandbox:
            print("\nRunning 'ls -la /' in sandbox:")
            ls_output, ls_error = e2b_auto.run_shell_command("ls -la /")
            # print(f"Output:\n{ls_output}")

            # print("\nAttempting to navigate to google.com (will run in background):")
            # e2b_auto.navigate_to("https://www.google.com") # Corrected https

            # print("\nWaiting a few seconds for Firefox to hopefully launch...")
            # import time
            # time.sleep(5) # Give browser time to open if it does

            print("\nAttempting to take a screenshot:")
            screenshot_file = e2b_auto.take_screenshot("test_screenshot.png")
            if screenshot_file:
                print(f"Screenshot saved to: {screenshot_file}")
            else:
                print("Failed to get screenshot.")

            # print("\nAttempting to click at (100,100) - visual feedback in E2B only")
            # e2b_auto.click_at_coords(100, 100)
            # time.sleep(1)

            # print("\nAttempting to type 'hello e2b' - visual feedback in E2B only")
            # e2b_auto.type_text("hello e2b")
            # time.sleep(1)

            # print("\nAttempting to press 'Return' key - visual feedback in E2B only")
            # e2b_auto.press_key("Return")

        else:
            print("Session could not be started or sandbox not available.")

    except Exception as e:
        print(f"An error occurred during the test: {e}")
    finally:
        if e2b_auto and e2b_auto._is_session_active: # Check e2b_auto exists
            print("\nClosing E2B session...")
            e2b_auto.close_session()
        print("Test script finished.")
