# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Setup

Before running the application, ensure you have the following prerequisites installed and configured:

### 1. Firefox
Firefox browser must be installed on your system and preferably accessible via the system's PATH. The application will attempt to locate it in common installation directories, but adding it to your PATH is the most reliable method.

### 2. Geckodriver (for Firefox Automation)

Selenium requires `geckodriver` to interact with Firefox. You must download the `geckodriver` executable and ensure it's in your system's PATH. The version of `geckodriver` should be compatible with your Firefox browser version.

1.  **Download Geckodriver:**
    *   Go to the official Mozilla Geckodriver releases page: [https://github.com/mozilla/geckodriver/releases](https://github.com/mozilla/geckodriver/releases)
    *   Download the correct version for your operating system and architecture (e.g., `geckodriver-vX.Y.Z-linux64.tar.gz` for 64-bit Linux, `geckodriver-vX.Y.Z-win64.zip` for 64-bit Windows).

2.  **Installation & PATH Setup (for Local Development):**

    *   **Linux:**
        1.  Open a terminal.
        2.  Extract the downloaded file: `tar -xvzf geckodriver-vX.Y.Z-linuxXX.tar.gz` (replace `vX.Y.Z-linuxXX` with the actual filename).
        3.  Make the `geckodriver` executable: `chmod +x geckodriver`.
        4.  Move the `geckodriver` executable to a directory in your system's PATH. Common choices include `/usr/local/bin` (requires sudo) or `~/.local/bin` (if it's in your PATH).
            *   Example (sudo): `sudo mv geckodriver /usr/local/bin/`
            *   Example (user local): `mkdir -p ~/.local/bin && mv geckodriver ~/.local/bin/` (ensure `~/.local/bin` is in your `~/.profile` or `~/.bashrc` PATH by adding `export PATH="$HOME/.local/bin:$PATH"` to it if not already present).
        5.  Verify installation: `geckodriver --version`.

    *   **macOS:**
        *   **Option 1: Homebrew (Recommended)**
            1.  Open a terminal.
            2.  Install Homebrew if you haven't already (see [https://brew.sh/](https://brew.sh/)).
            3.  Install `geckodriver`: `brew install geckodriver`.
            4.  Verify installation: `geckodriver --version`.
        *   **Option 2: Manual Download**
            1.  Download the macOS `.tar.gz` file from the releases page.
            2.  Extract it: `tar -xvzf geckodriver-vX.Y.Z-macos.tar.gz` (replace `vX.Y.Z-macos` with the actual filename).
            3.  Make executable: `chmod +x geckodriver`.
            4.  Move to a directory in PATH (e.g., `/usr/local/bin`). Example: `sudo mv geckodriver /usr/local/bin/`.
            5.  Verify installation: `geckodriver --version`.
            *Note for macOS Catalina and newer: If you encounter a security warning stating that "geckodriver cannot be opened because the developer cannot be verified," you may need to remove the quarantine attribute. Open System Preferences > Security & Privacy > General, and you should see a message about `geckodriver` being blocked. Click "Allow Anyway". Alternatively, run `xattr -d com.apple.quarantine /path/to/geckodriver` (replace `/path/to/geckodriver` with the actual path, e.g., `/usr/local/bin/geckodriver`).*

    *   **Windows:**
        1.  Extract the `geckodriver.exe` file from the downloaded `.zip` archive (e.g., using Windows File Explorer's built-in "Extract All..." option or a tool like 7-Zip).
        2.  Move `geckodriver.exe` to a directory that is part of your system's PATH.
            *   It's good practice to create a dedicated directory for WebDriver executables (e.g., `C:\WebDriver\bin`) and add this directory to your PATH.
            *   Alternatively, you can place it in an existing directory already in PATH (e.g., `C:\Windows\System32`), though this is less recommended for user-installed executables.
        3.  To add a directory to your PATH:
            *   Search for "environment variables" in the Start Menu.
            *   Click "Edit the system environment variables" (or "Edit environment variables for your account").
            *   In the System Properties window, click the "Environment Variables..." button.
            *   Under "System variables" (for all users) or "User variables" (for the current user), find the variable named `Path` (or `PATH`), select it, and click "Edit...".
            *   Click "New" and add the full path to the directory where you placed `geckodriver.exe` (e.g., `C:\WebDriver\bin`).
            *   Click "OK" on all open dialog windows to save the changes.
        4.  Verify installation: Open a **new** Command Prompt or PowerShell window (existing windows will not reflect PATH changes) and type `geckodriver --version`.

3.  **Verify Geckodriver Installation (for Local Development):**
    After installation and PATH configuration, close and reopen any terminal/command prompt windows. Type `geckodriver --version` and press Enter. You should see output similar to `geckodriver X.Y.Z` (where X.Y.Z is the version number). If you see an error like "geckodriver is not recognized as an internal or external command..." or "command not found: geckodriver", the directory containing the `geckodriver` executable is not correctly configured in your system's PATH. Double-check your PATH settings.

### Note for Streamlit Cloud Deployments (and similar platforms):

If you are deploying this application on Streamlit Cloud or a similar platform that uses `apt` for system dependencies via a `packages.txt` file:
*   Ensure your `packages.txt` file includes:
    ```
    libgl1
    firefox-esr
    firefox-geckodriver
    ```
*   The platform will automatically install these packages using `apt-get`. The manual `geckodriver` download and PATH setup instructions above are primarily for local development environments.
*   If you encounter browser startup issues in your deployment, ensure these package names are correct (e.g., `firefox-geckodriver` vs. `geckodriver`) and are supported by the platform's base image (e.g., Streamlit Cloud's default Debian-based Linux environment).
*   The `geckodriver.log` file (if created in the deployment environment) can still be a source of diagnostic information, though accessing logs might vary by platform. Check your platform's documentation for log access.

**Troubleshooting Startup Issues:**
The application is configured to use `geckodriver` (either from PATH in local development or via installed package in deployments). If you encounter errors during browser startup (e.g., timeout errors), please verify the following:
*   **Local Development:**
    *   Both Firefox and Geckodriver are correctly installed.
    *   The version of Geckodriver is compatible with your Firefox version. (Check the Geckodriver release notes for Firefox compatibility.)
    *   Geckodriver is accessible via the PATH (as verified above).
*   **Cloud Deployment:**
    *   The packages in `packages.txt` are correctly named and installed by the platform.
    *   The Firefox version provided by `firefox-esr` is compatible with the `firefox-geckodriver` version.
*   **General:**
    *   Review the `geckodriver.log` file for specific error messages. For local development, this file is created in the application's working directory. For cloud deployments, its location and accessibility depend on the platform.

The application generates a `geckodriver.log` file in its working directory. This log file can provide valuable diagnostic information if you experience problems with Firefox startup or WebDriver interactions. Check this file for specific error messages from Geckodriver.
