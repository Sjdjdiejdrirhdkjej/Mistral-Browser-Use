import requests
import json
import base64
import os
import subprocess
import time
import signal
from pathlib import Path

# Global variable to store the server process handle
ollama_server_process = None
DEFAULT_OLLAMA_API_BASE_URL = "http://localhost:11434/api" # Consistent with OllamaClient
DEFAULT_OLLAMA_BASE_URL_FOR_RESPONSIVENESS = "http://localhost:11434" # Root for general responsiveness check

def is_ollama_server_responsive(base_url=DEFAULT_OLLAMA_BASE_URL_FOR_RESPONSIVENESS):
    """Checks if the Ollama server is responsive."""
    try:
        response = requests.get(base_url, timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        # print("Ollama server: Connection error.") # Reduced verbosity
        return False
    except Exception as e:
        # print(f"Ollama server: An unexpected error occurred while checking responsiveness: {e}") # Reduced verbosity
        return False

def start_ollama_server():
    """Starts the Ollama server if not already running."""
    global ollama_server_process

    if ollama_server_process and ollama_server_process.poll() is None:
        if is_ollama_server_responsive():
            # print("Ollama server is already running and responsive.") # Reduced verbosity
            return True
        else:
            print("Ollama server process exists but is not responsive. Attempting to stop and restart.")
            stop_ollama_server() # Attempt to clean up

    print("Starting Ollama server...")
    try:
        preexec_fn = os.setsid if os.name != 'nt' else None
        ollama_server_process = subprocess.Popen(
            ['ollama', 'serve'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=preexec_fn
        )
        # print(f"Ollama server process started with PID: {ollama_server_process.pid}.") # Reduced verbosity

        max_wait_time = 15
        wait_interval = 1
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            time.sleep(wait_interval)
            elapsed_time += wait_interval
            # print(f"Waiting for Ollama server to be responsive... ({elapsed_time}s)") # Reduced verbosity
            if is_ollama_server_responsive():
                print("Ollama server started and is responsive.")
                return True

        print(f"Ollama server did not become responsive within {max_wait_time} seconds.")
        stop_ollama_server()
        return False

    except FileNotFoundError:
        print("Error: The 'ollama' command was not found. Please ensure Ollama is installed and in your PATH.")
        ollama_server_process = None
        return False
    except Exception as e:
        print(f"An error occurred while trying to start the Ollama server: {e}")
        if ollama_server_process:
            stop_ollama_server()
        ollama_server_process = None
        return False

def stop_ollama_server():
    """Stops the Ollama server if it's running."""
    global ollama_server_process

    if ollama_server_process and ollama_server_process.poll() is None:
        # print(f"Stopping Ollama server process (PID: {ollama_server_process.pid})...") # Reduced verbosity
        try:
            if os.name == 'nt':
                ollama_server_process.terminate()
                # print("Sent terminate signal to Ollama server on Windows.") # Reduced verbosity
            else:
                os.killpg(os.getpgid(ollama_server_process.pid), signal.SIGINT)
                # print(f"Sent SIGINT to Ollama server process group (PGID: {os.getpgid(ollama_server_process.pid)}).") # Reduced verbosity

            ollama_server_process.wait(timeout=15)
            print("Ollama server process terminated.")
            ollama_server_process = None
            return True
        except subprocess.TimeoutExpired:
            print("Timeout expired while waiting for Ollama server to terminate. Forcing kill.")
            if os.name == 'nt':
                 ollama_server_process.kill()
            else:
                try:
                    os.killpg(os.getpgid(ollama_server_process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    print("Process group already terminated.")
            ollama_server_process.wait()
            ollama_server_process = None
            return False
        except ProcessLookupError:
            print("Ollama server process already terminated (ProcessLookupError).")
            ollama_server_process = None
            return True
        except Exception as e:
            print(f"An error occurred while stopping the Ollama server: {e}")
            if ollama_server_process and ollama_server_process.poll() is None:
                try:
                    if os.name == 'nt':
                        ollama_server_process.kill()
                    else:
                        os.killpg(os.getpgid(ollama_server_process.pid), signal.SIGKILL)
                    ollama_server_process.wait()
                except Exception as kill_e:
                    print(f"Error during force kill: {kill_e}")
            ollama_server_process = None
            return False
    else:
        # print("Ollama server process is not running or handle is invalid.") # Reduced verbosity
        ollama_server_process = None
        return True

def pull_model_via_ollama(model_name: str):
    """Pulls a model using the 'ollama pull' command."""
    if not is_ollama_server_responsive():
        return False, "Ollama server not running or not responsive."

    # print(f"Pulling Ollama model: {model_name}...") # Reduced verbosity
    try:
        result = subprocess.run(
            ['ollama', 'pull', model_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=300
        )
        if result.returncode == 0:
            # print(f"Model '{model_name}' pulled successfully.") # Reduced verbosity
            return True, f"Model '{model_name}' pulled successfully."
        else:
            error_message = result.stderr.strip() if result.stderr else "Unknown error during ollama pull."
            # print(f"Failed to pull model '{model_name}'. Error: {error_message}") # Reduced verbosity
            return False, f"Failed to pull model '{model_name}': {error_message}"
    except FileNotFoundError:
        return False, "The 'ollama' command was not found. Please ensure Ollama is installed and in your PATH."
    except subprocess.TimeoutExpired:
        return False, f"Timeout expired while trying to pull model '{model_name}'."
    except Exception as e:
        return False, f"An unexpected error occurred during 'ollama pull {model_name}': {e}"

def check_model_pulled_via_ollama_api(model_name: str, base_url=DEFAULT_OLLAMA_API_BASE_URL):
    """Checks if a model has been pulled using the Ollama API /api/tags."""
    if not is_ollama_server_responsive():
        #  print("Cannot check model: Ollama server not responsive.") # Reduced verbosity
         return False

    try:
        response = requests.get(f"{base_url}/tags", timeout=10)
        response.raise_for_status()

        data = response.json()
        if "models" in data and isinstance(data["models"], list):
            for model_info in data["models"]:
                if model_info.get("name", "").startswith(model_name):
                    return True
            return False
        else:
            # print(f"Unexpected response format from Ollama API /api/tags: {data}") # Reduced verbosity
            return False

    except requests.exceptions.Timeout:
        # print(f"Timeout while trying to connect to Ollama API at {base_url}/tags.") # Reduced verbosity
        return False
    except requests.exceptions.RequestException as e:
        # print(f"Error connecting to Ollama API at {base_url}/tags: {e}") # Reduced verbosity
        return False
    except json.JSONDecodeError:
        # print(f"Failed to decode JSON response from {base_url}/tags.") # Reduced verbosity
        return False
    except Exception as e:
        # print(f"An unexpected error occurred while checking model '{model_name}': {e}") # Reduced verbosity
        return False

def get_ollama_model_file_path(model_name: str):
    if ":" not in model_name:
        model_name_with_tag = f"{model_name}:latest"
    else:
        model_name_with_tag = model_name
    try:
        ollama_models_dir_env = os.getenv("OLLAMA_MODELS")
        if ollama_models_dir_env:
            models_base_dir = Path(ollama_models_dir_env)
        else:
            models_base_dir = Path.home() / ".ollama" / "models"

        parts = model_name_with_tag.split(':')
        name_part = parts[0]
        tag_part = parts[1]

        if '/' in name_part:
            manifest_model_path_part = name_part
        else:
            manifest_model_path_part = f"registry.ollama.ai/library/{name_part}"

        manifest_path = models_base_dir / "manifests" / manifest_model_path_part / tag_part

        if not manifest_path.exists():
            simple_manifest_path_obj = models_base_dir / "manifests" / name_part / tag_part
            if simple_manifest_path_obj.exists():
                manifest_path = simple_manifest_path_obj
            else:
                initial_checked_path_str = str(models_base_dir / "manifests" / manifest_model_path_part / tag_part)
                return None, f"Manifest file not found. Checked: {initial_checked_path_str} and {str(simple_manifest_path_obj)}"

        if not manifest_path.is_file():
            return None, f"Manifest path found ('{str(manifest_path)}') but is not a file."

        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)

        model_layer_digest = None
        priority_media_types = ["application/vnd.ollama.image.model", "application/vnd.ollama.image.gguf"]
        for layer in manifest_data.get('layers', []):
            if layer.get('mediaType') in priority_media_types:
                model_layer_digest = layer.get('digest')
                break
        if not model_layer_digest:
            for layer in manifest_data.get('layers', []):
                if layer.get('digest'):
                    model_layer_digest = layer.get('digest')
                    # print(f"Warning: Using a generic layer digest {model_layer_digest} as primary model types not found.") # Reduced verbosity
                    break
            if not model_layer_digest:
                 return None, "Compatible model layer with a digest not found in manifest."

        blob_filename = model_layer_digest.replace(":", "-")
        blob_file_path = models_base_dir / "blobs" / blob_filename

        if blob_file_path.is_file():
            return str(blob_file_path), "Model file found."
        else:
            return None, f"Model blob file not found at expected path: {str(blob_file_path)}"
    except FileNotFoundError:
        return None, f"Manifest file related FileNotFoundError."
    except json.JSONDecodeError:
        return None, f"Error decoding JSON from manifest file."
    except Exception as e:
        return None, f"An unexpected error occurred: {e}"

class OllamaClient:
    def __init__(self, base_url=DEFAULT_OLLAMA_API_BASE_URL):
        self.base_url = base_url
    def generate_completion(self, prompt: str, model_name: str = "llama2", image_base64: str = None, options: dict = None):
        if not is_ollama_server_responsive():
            # print("Ollama server is not running or not responsive. Cannot generate completion.") # Reduced verbosity
            return None
        try:
            headers = {"Content-Type": "application/json"}
            payload = {"model": model_name, "prompt": prompt, "stream": False}
            if image_base64: payload["images"] = [image_base64]
            if options: payload["options"] = options
            response = requests.post(f"{self.base_url}/generate", headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result.get("response")
        except requests.exceptions.Timeout:
            # print(f"API request timed out in generate_completion for model {model_name}.") # Reduced verbosity
            return None
        except requests.exceptions.RequestException as e:
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    if "error" in error_data and "model" in error_data["error"] and "not found" in error_data["error"]:
                        # print(f"Model '{model_name}' not found. Please pull it first using 'ollama pull {model_name}'.") # Reduced verbosity
                        return None
                except json.JSONDecodeError: pass
            # print(f"API request failed in generate_completion (model: {model_name}): {str(e)}. Response text: {e.response.text if e.response else 'N/A'}") # Reduced verbosity
            return None
        except Exception as e:
            # print(f"Error in generate_completion (model: {model_name}): {str(e)}") # Reduced verbosity
            return None
    def list_models(self):
        if not is_ollama_server_responsive():
            #  print("Ollama server is not running or not responsive. Cannot list models.") # Reduced verbosity
             return None
        try:
            response = requests.get(f"{self.base_url}/tags", timeout=10)
            response.raise_for_status()
            models_data = response.json()
            if "models" in models_data and isinstance(models_data["models"], list):
                return [model.get("name") for model in models_data["models"] if model.get("name")]
            else:
                # print(f"Unexpected response format from /api/tags: {models_data}") # Reduced verbosity
                return []
        except requests.exceptions.Timeout:
            # print("API request timed out while listing models.") # Reduced verbosity
            return None
        except requests.exceptions.RequestException as e:
            # print(f"API request failed while listing models: {str(e)}. Response text: {e.response.text if e.response else 'N/A'}") # Reduced verbosity
            return None
        except json.JSONDecodeError:
            # print(f"Failed to decode JSON response from {self.base_url}/tags.") # Reduced verbosity
            return None
        except Exception as e:
            # print(f"Error listing models: {str(e)}") # Reduced verbosity
            return None
