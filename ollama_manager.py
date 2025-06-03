import subprocess
import time
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

OLLAMA_PROCESS = None

def is_ollama_running():
    """Checks if an Ollama server process seems to be running and responding."""
    try:
        # Use ollama list as a proxy to see if server is up
        # This requires the ollama CLI to be available and implicitly checks server response
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10, check=False)
        if result.returncode == 0:
            logging.info("Ollama server appears to be running and responding.")
            return True
        else:
            logging.info(f"'ollama list' command failed or returned error (code {result.returncode}), assuming server not ready: {result.stderr}")
            return False
    except FileNotFoundError:
        logging.error("Ollama command not found. Ensure Ollama is installed and in PATH.")
        return False
    except subprocess.TimeoutExpired:
        logging.error("'ollama list' timed out. Server might be unresponsive.")
        return False
    except Exception as e:
        logging.error(f"Error checking Ollama status with 'ollama list': {e}")
        return False

def start_ollama_serve():
    """Starts 'ollama serve' as a background process if not already running."""
    global OLLAMA_PROCESS
    if OLLAMA_PROCESS and OLLAMA_PROCESS.poll() is None:
        logging.info("'ollama serve' process already managed and running.")
        if is_ollama_running(): # Double check if it's responsive
            return True
        else:
            logging.warning("Managed 'ollama serve' process exists but server not responding. Attempting to restart.")
            OLLAMA_PROCESS.terminate()
            try:
                OLLAMA_PROCESS.wait(timeout=5)
            except subprocess.TimeoutExpired:
                OLLAMA_PROCESS.kill()
            OLLAMA_PROCESS = None

    if is_ollama_running():
        logging.info("An Ollama server is already running and responsive (not managed by this app). Will use it.")
        # We don't assign to OLLAMA_PROCESS here as we didn't start it.
        return True

    logging.info("Attempting to start 'ollama serve' in the background...")
    try:
        # For Windows, might need specific creationflags if a new console window is an issue
        # creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        # Using shell=True can be a security risk if command is from untrusted input, but ollama serve is fixed.
        # However, it's generally better to avoid shell=True if possible.
        # Let's try without shell=True first.
        OLLAMA_PROCESS = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
            # creationflags=creationflags
        )
        logging.info(f"'ollama serve' started with PID: {OLLAMA_PROCESS.pid}. Waiting for it to be ready...")

        # Wait a bit for the server to initialize
        time.sleep(5) # Initial delay

        # Check responsiveness
        max_retries = 5
        retry_delay = 3 # seconds
        for attempt in range(max_retries):
            if is_ollama_running():
                logging.info("'ollama serve' is up and responding.")
                return True
            logging.info(f"Server not yet responsive. Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

        logging.error("'ollama serve' started but did not become responsive in time.")
        # Try to terminate the process if it started but isn't responsive
        if OLLAMA_PROCESS.poll() is None: # Check if process is still running
            OLLAMA_PROCESS.terminate()
            try:
                OLLAMA_PROCESS.wait(timeout=5)
            except subprocess.TimeoutExpired:
                OLLAMA_PROCESS.kill()
        OLLAMA_PROCESS = None
        return False

    except FileNotFoundError:
        logging.error("Ollama command not found. Cannot start 'ollama serve'. Ensure Ollama is installed and in PATH.")
        OLLAMA_PROCESS = None
        return False
    except Exception as e:
        logging.error(f"Failed to start 'ollama serve': {e}")
        if OLLAMA_PROCESS and OLLAMA_PROCESS.poll() is None:
            OLLAMA_PROCESS.terminate()
            OLLAMA_PROCESS.kill() # Ensure it's killed if termination fails
        OLLAMA_PROCESS = None
        return False

def ensure_deepseek_model():
    """Ensures the 'deepseek-r1' model is available, pulling it if necessary."""
    model_name = "deepseek-r1" # Hardcoded as per new requirements
    try:
        # Check if model is already available using 'ollama list'
        logging.info(f"Checking if model '{model_name}' is available locally...")
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=30, check=False)
        if result.returncode == 0 and model_name in result.stdout:
            logging.info(f"Model '{model_name}' is already available.")
            return True
        elif result.returncode != 0:
            logging.warning(f"'ollama list' command failed while checking for {model_name}. Proceeding to pull. Error: {result.stderr}")

        logging.info(f"Model '{model_name}' not found locally or list failed. Attempting to pull '{model_name}'...")
        # Using subprocess.run for pull as it's a blocking operation
        pull_process = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            timeout=300 # Allow up to 5 minutes for model download
        )
        if pull_process.returncode == 0:
            logging.info(f"Model '{model_name}' pulled successfully.")
            return True
        else:
            logging.error(f"Failed to pull model '{model_name}'. Return code: {pull_process.returncode}")
            logging.error(f"Stderr: {pull_process.stderr}")
            logging.error(f"Stdout: {pull_process.stdout}")
            return False
    except FileNotFoundError:
        logging.error(f"Ollama command not found. Cannot ensure model '{model_name}'. Ensure Ollama is installed and in PATH.")
        return False
    except subprocess.TimeoutExpired:
        logging.error(f"Timeout while trying to pull model '{model_name}'.")
        return False
    except Exception as e:
        logging.error(f"An error occurred while ensuring model '{model_name}': {e}")
        return False

def stop_ollama_serve():
    """Stops the managed 'ollama serve' process if it's running."""
    global OLLAMA_PROCESS
    if OLLAMA_PROCESS and OLLAMA_PROCESS.poll() is None:
        logging.info(f"Attempting to stop managed 'ollama serve' process (PID: {OLLAMA_PROCESS.pid})...")
        OLLAMA_PROCESS.terminate() # Send SIGTERM
        try:
            OLLAMA_PROCESS.wait(timeout=10) # Wait for graceful shutdown
            logging.info("'ollama serve' process terminated gracefully.")
        except subprocess.TimeoutExpired:
            logging.warning("'ollama serve' did not terminate gracefully. Sending SIGKILL...")
            OLLAMA_PROCESS.kill() # Force kill
            logging.info("'ollama serve' process killed.")
        OLLAMA_PROCESS = None
    else:
        logging.info("No managed 'ollama serve' process to stop or it's already stopped.")

# Example of how to use these (for testing manager directly, not part of app.py)
if __name__ == '__main__':
    logging.info("--- Ollama Manager Direct Test --- ")
    if start_ollama_serve():
        logging.info("Ollama server started or was already running.")
        if ensure_deepseek_model():
            logging.info("Deepseek model ensured.")
        else:
            logging.error("Failed to ensure deepseek model.")
        # Keep it running for a bit for testing, then stop
        logging.info("Keeping server alive for 15 seconds for manual check...")
        time.sleep(15)
        stop_ollama_serve()
    else:
        logging.error("Failed to start Ollama server.")
    logging.info("--- Test Complete --- ")
