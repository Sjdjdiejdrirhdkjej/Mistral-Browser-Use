import os
import subprocess
import platform
import shutil
from datetime import datetime
import base64
import json

def find_firefox_binary():
    """Find Firefox binary across different systems"""
    system = platform.system().lower()
    
    if system == "linux":
        possible_paths = [
            '/usr/bin/firefox',
            '/usr/local/bin/firefox',
            '/opt/firefox/firefox',
            '/snap/bin/firefox',
            shutil.which('firefox')
        ]
    elif system == "darwin":  # macOS
        possible_paths = [
            '/Applications/Firefox.app/Contents/MacOS/firefox',
            '/usr/local/bin/firefox',
            shutil.which('firefox')
        ]
    elif system == "windows":
        possible_paths = [
            'C:\\Program Files\\Mozilla Firefox\\firefox.exe',
            'C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe',
            shutil.which('firefox.exe')
        ]
    else:
        possible_paths = [shutil.which('firefox')]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            return path
    
    # Try using system commands
    try:
        if system in ["linux", "darwin"]:
            result = subprocess.run(['which', 'firefox'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        elif system == "windows":
            result = subprocess.run(['where', 'firefox'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    return None

def ensure_directory_exists(directory_path):
    """Ensure a directory exists, create if it doesn't"""
    os.makedirs(directory_path, exist_ok=True)
    return directory_path

def generate_timestamp():
    """Generate a timestamp string for file naming"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def encode_image_to_base64(image_path):
    """Encode an image file to base64 string"""
    try:
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        raise Exception(f"Failed to encode image: {str(e)}")

def save_json_data(data, filepath):
    """Save data as JSON file"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        print(f"Failed to save JSON data: {str(e)}")
        return False

def load_json_data(filepath):
    """Load data from JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load JSON data: {str(e)}")
        return None

def clean_old_screenshots(directory='screenshots', max_files=50):
    """Clean old screenshot files to prevent disk space issues"""
    try:
        if not os.path.exists(directory):
            return
        
        files = []
        for filename in os.listdir(directory):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(directory, filename)
                files.append((filepath, os.path.getctime(filepath)))
        
        # Sort by creation time (oldest first)
        files.sort(key=lambda x: x[1])
        
        # Remove oldest files if we exceed max_files
        while len(files) > max_files:
            oldest_file = files.pop(0)
            try:
                os.remove(oldest_file[0])
                print(f"Removed old screenshot: {oldest_file[0]}")
            except:
                pass
                
    except Exception as e:
        print(f"Error cleaning old screenshots: {str(e)}")

def validate_url(url):
    """Validate and normalize URL"""
    if not url:
        return None
    
    url = url.strip()
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Basic validation
    if '.' not in url:
        return None
    
    return url

def get_system_info():
    """Get basic system information for debugging"""
    info = {
        'platform': platform.system(),
        'architecture': platform.architecture(),
        'python_version': platform.python_version(),
        'firefox_binary': find_firefox_binary()
    }
    return info

def format_error_message(error, context=""):
    """Format error message for user display"""
    error_str = str(error)
    
    # Common error translations
    if "connection refused" in error_str.lower():
        return f"Unable to connect to the service. Please check your internet connection. {context}"
    elif "timeout" in error_str.lower():
        return f"The operation timed out. Please try again. {context}"
    elif "not found" in error_str.lower():
        return f"Required component not found. Please check your installation. {context}"
    elif "permission denied" in error_str.lower():
        return f"Permission denied. Please check file permissions. {context}"
    else:
        return f"An error occurred: {error_str} {context}"

def log_automation_step(step_number, action, result, timestamp=None):
    """Log automation steps for debugging"""
    if timestamp is None:
        timestamp = datetime.now()
    
    log_entry = {
        'step': step_number,
        'timestamp': timestamp.isoformat(),
        'action': action,
        'result': result
    }
    
    # Ensure logs directory exists
    ensure_directory_exists('logs')
    
    # Save to log file
    log_file = os.path.join('logs', f"automation_{generate_timestamp()}.json")
    
    try:
        logs = []
        if os.path.exists(log_file):
            logs = load_json_data(log_file) or []
        
        logs.append(log_entry)
        save_json_data(logs, log_file)
    except:
        pass  # Don't fail automation if logging fails
    
    return log_entry
