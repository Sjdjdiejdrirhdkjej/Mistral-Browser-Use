import shutil
import requests
import subprocess
import time
import streamlit as st
import os

def is_ollama_installed() -> bool:
    """Checks if the 'ollama' command-line tool is installed and in the PATH."""
    return shutil.which('ollama') is not None

def is_ollama_server_running() -> bool:
    """Checks if the Ollama server is responsive on the default port."""
    try:
        # Check a common Ollama API endpoint that indicates the server is up.
        # Using /api/tags is often a good choice as it's simple and should always be available.
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        # Ollama might return 200 even if no models, or other statuses for specific errors.
        # We are primarily checking for reachability.
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def start_ollama_server_for_pull() -> subprocess.Popen | None:
    """Attempts to start the 'ollama serve' command as a background process."""
    if is_ollama_server_running():
        # Do not show st.info here as this function might be called internally
        # print("Ollama server already running.")
        return None # Indicates server was already running

    if not is_ollama_installed():
        st.error("Ollama is not installed. Cannot start server for pull.")
        return None

    try:
        # Use st.info for user feedback in the Streamlit app context if called from there
        # print("Attempting to start Ollama server temporarily for model download...")
        # For Windows, shell=True might be needed if 'ollama' is a batch file or similar.
        # For Linux/macOS, shell=False is safer.
        # Redirecting stdout/stderr to DEVNULL to prevent blocking or outputting to Streamlit console directly.
        process = subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for the server to initialize. This is crucial.
        max_wait_time = 15  # seconds
        poll_interval = 0.5 # seconds
        waited_time = 0

        with st.spinner("Waiting for temporary Ollama server to start..."):
            while waited_time < max_wait_time:
                if is_ollama_server_running():
                    st.success("Ollama server started temporarily.")
                    return process # Return process handle to stop it later
                time.sleep(poll_interval)
                waited_time += poll_interval

        # If loop finishes, server didn't start in time
        st.error(f"Ollama server did not start within {max_wait_time} seconds.")
        try: # Attempt to clean up the process if it started but isn't responsive
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            pass # Ignore errors during cleanup attempt
        return None

    except FileNotFoundError: # Should be caught by is_ollama_installed ideally
        st.error("Ollama command not found. Cannot start server for pull.")
        return None
    except Exception as e:
        st.error(f"Error starting Ollama server for pull: {e}")
        return None

def stop_ollama_server_after_pull(process: subprocess.Popen | None):
    """Stops the temporary Ollama server if a process handle is provided."""
    if process:
        try:
            # print("Stopping temporary Ollama server...")
            process.terminate()
            try:
                process.wait(timeout=10) # Wait for termination
                # print("Temporary Ollama server stopped.")
                st.info("Temporary Ollama server has been stopped.")
            except subprocess.TimeoutExpired:
                st.warning("Temporary Ollama server did not terminate quickly. It might need to be stopped manually if still running.")
                process.kill() # Force kill if terminate didn't work
                process.wait(timeout=5)
        except Exception as e:
            st.warning(f"Error stopping temporary Ollama server: {e}. It might need to be stopped manually.")

def ensure_model_pulled(model_name: str) -> bool:
    """
    Ensures the specified Ollama model is pulled.
    Starts and stops Ollama server temporarily if not already running.
    """
    if not is_ollama_installed():
        st.error(f"Ollama CLI not installed. Cannot pull model '{model_name}'.")
        return False

    # 1. Check if model is already available
    try:
        # Use 'ollama list' to check for the model.
        # This requires the server to be running.
        server_was_running = is_ollama_server_running()
        temp_server_proc = None

        if not server_was_running:
            temp_server_proc = start_ollama_server_for_pull()
            if temp_server_proc is None and not is_ollama_server_running():
                st.error(f"Ollama server is not running and could not be started. Cannot check or pull '{model_name}'.")
                return False

        # Now that server is assumed running (either was or started)
        list_result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, check=False)
        if list_result.returncode == 0 and model_name in list_result.stdout:
            st.success(f"Model '{model_name}' is already available locally.")
            if temp_server_proc: # If we started it
                stop_ollama_server_after_pull(temp_server_proc)
            return True
        elif list_result.returncode != 0:
             st.warning(f"Could not execute 'ollama list' (Error: {list_result.stderr.strip()}). Will attempt to pull '{model_name}' directly.")

    except Exception as e:
        st.warning(f"Could not check if model '{model_name}' is available via 'ollama list': {e}. Will attempt to pull.")
        # Ensure server is stopped if we started it and an error occurred here
        if 'temp_server_proc' in locals() and temp_server_proc:
             stop_ollama_server_after_pull(temp_server_proc)
             # Reset temp_server_proc as we might start it again for the pull
             temp_server_proc = None


    # 2. If model not found or list failed, attempt to pull
    st.info(f"Attempting to pull model '{model_name}'. This may take some time...")

    server_proc_for_pull = None # Separate variable for clarity
    if not is_ollama_server_running():
        server_proc_for_pull = start_ollama_server_for_pull()
        if server_proc_for_pull is None and not is_ollama_server_running(): # Check again
            st.error(f"Ollama server not running and could not be started. Cannot pull '{model_name}'.")
            return False

    pull_success = False
    try:
        # Use st.progress for visual feedback if possible, but subprocess makes it tricky.
        # For now, just run and wait.
        # Using st.empty() to show live output from ollama pull
        progress_placeholder = st.empty()
        progress_placeholder.info(f"Starting pull process for {model_name}...")

        # Start the pull process
        process = subprocess.Popen(['ollama', 'pull', model_name],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, # Redirect stderr to stdout
                                   text=True,
                                   bufsize=1, # Line buffered
                                   encoding='utf-8')

        # Stream the output
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line.strip())
            # Display the last few lines of output
            progress_placeholder.info(f"Pulling {model_name}...\n" + "\n".join(output_lines[-5:]))

        process.stdout.close()
        return_code = process.wait()

        if return_code == 0:
            st.success(f"Model '{model_name}' pulled successfully.")
            # st.text_area("Full Pull Output:", "".join(output_lines), height=200) # Optional: show full log
            pull_success = True
        else:
            st.error(f"Failed to pull model '{model_name}'. Return code: {return_code}")
            st.text_area("Pull Error Output:", "".join(output_lines), height=200)

    except FileNotFoundError:
        st.error("Ollama command not found during pull. Ensure Ollama is installed and in PATH.")
    except Exception as e:
        st.error(f"An unexpected error occurred during model pull: {e}")
    finally:
        progress_placeholder.empty() # Clear the progress message
        if server_proc_for_pull: # If we started the server specifically for this pull
            stop_ollama_server_after_pull(server_proc_for_pull)

    return pull_success

```
