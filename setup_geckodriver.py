import os
import stat
import tarfile
import urllib.request
import shutil

GECKODRIVER_VERSION = "v0.36.0"
GECKODRIVER_URL = f"https://github.com/mozilla/geckodriver/releases/download/{GECKODRIVER_VERSION}/geckodriver-{GECKODRIVER_VERSION}-linux64.tar.gz"
GECKODRIVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "bin"))
GECKODRIVER_PATH = os.path.join(GECKODRIVER_DIR, "geckodriver")

def download_and_install_geckodriver():
    """Downloads, extracts, and installs geckodriver if not already present, then adds it to PATH."""
    if os.path.exists(GECKODRIVER_PATH):
        print(f"Geckodriver already installed at {GECKODRIVER_PATH}")
        # Ensure it's executable
        st = os.stat(GECKODRIVER_PATH)
        if not (st.st_mode & stat.S_IEXEC):
            print("Making geckodriver executable...")
            os.chmod(GECKODRIVER_PATH, st.st_mode | stat.S_IEXEC)
        add_to_path()
        return

    print(f"Geckodriver not found. Downloading from {GECKODRIVER_URL}...")
    os.makedirs(GECKODRIVER_DIR, exist_ok=True)

    tar_path = os.path.join(GECKODRIVER_DIR, "geckodriver.tar.gz") # Define tar_path outside try for cleanup
    try:
        # Download the tar.gz file
        urllib.request.urlretrieve(GECKODRIVER_URL, tar_path)
        print(f"Downloaded to {tar_path}")

        # Extract the geckodriver binary
        with tarfile.open(tar_path, "r:gz") as tar:
            # Ensure geckodriver is extracted directly into GECKODRIVER_DIR
            # The tar file usually contains the geckodriver binary at the root.
            member = tar.getmember("geckodriver") # Assuming the binary is named 'geckodriver' in the archive
            member.name = os.path.basename(GECKODRIVER_PATH) # Ensure it's extracted as 'geckodriver'
            tar.extract(member, GECKODRIVER_DIR)

        print(f"Extracted geckodriver to {GECKODRIVER_PATH}")

        # Make it executable
        os.chmod(GECKODRIVER_PATH, 0o755) # rwxr-xr-x
        print(f"Set geckodriver as executable at {GECKODRIVER_PATH}")

        # Clean up the tar.gz file
        os.remove(tar_path)
        print(f"Removed {tar_path}")

        add_to_path()

    except Exception as e:
        print(f"Error installing geckodriver: {e}")
        # Clean up partially downloaded files or extracted files if error occurs
        if os.path.exists(tar_path):
            os.remove(tar_path)
        if os.path.exists(GECKODRIVER_PATH):
            os.remove(GECKODRIVER_PATH)
        # It's important to raise the error or handle it such that the app doesn't try to run selenium
        raise

def add_to_path():
    """Adds the geckodriver directory to the PATH environment variable."""
    # Check if GECKODRIVER_DIR is part of the PATH
    env_path = os.environ.get("PATH", "")
    if GECKODRIVER_DIR not in env_path.split(os.pathsep):
        os.environ["PATH"] = f"{GECKODRIVER_DIR}{os.pathsep}{env_path}"
        print(f"Added {GECKODRIVER_DIR} to PATH.")
    # Always print the current PATH for verification, especially in containerized environments
    print(f"Current PATH: {os.environ.get('PATH', 'PATH environment variable not set')}")


if __name__ == "__main__":
    download_and_install_geckodriver()
    # To test, you could try importing selenium here and starting Firefox
    # from selenium import webdriver
    # try:
    #     print("Attempting to start Firefox with geckodriver from script...")
    #     driver = webdriver.Firefox()
    #     print("Firefox started successfully via geckodriver.")
    #     driver.quit()
    # except Exception as e:
    #     print(f"Error starting Firefox with geckodriver: {e}")
