# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Setup

Before running the application, ensure you have the following prerequisites installed and configured:

### 1. Python Environment
Ensure you have Python installed. This project uses a `requirements.txt` file to manage Python dependencies. It's recommended to use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

### 2. Firefox Browser

*   **Local Development:**
    Firefox browser must be installed on your system. The application will attempt to locate it in common installation directories. If not found, ensure Firefox is in your system's PATH or provide the correct binary location if you modify the script.
*   **Cloud Deployments (e.g., Streamlit Cloud):**
    Firefox (specifically `firefox-esr`) is installed via the `packages.txt` file. See the deployment notes below.

### 3. Geckodriver (for Firefox Automation)

Geckodriver is required for Selenium to control Firefox. This project uses `webdriver-manager` (listed in `requirements.txt`) to automatically download and manage the correct version of Geckodriver. When the application starts, `webdriver-manager` will download `geckodriver` to a cache directory and use it.

*   **Primary Method:** `webdriver-manager` handles this automatically. No manual download or PATH setup for `geckodriver` is typically needed.
*   **Fallback/Troubleshooting:** If `webdriver-manager` encounters issues (e.g., network problems, unusual system setup), you might need to:
    1.  Download `geckodriver` manually from the [Mozilla Geckodriver releases page](https://github.com/mozilla/geckodriver/releases).
    2.  Ensure the downloaded `geckodriver` executable is in your system's PATH.
    This should only be necessary if the automatic management fails.

The application is configured to run Firefox in **headless mode** (no visible browser window), which is suitable for server deployments.

### Note for Streamlit Cloud Deployments (and similar platforms):

If you are deploying this application on Streamlit Cloud or a similar platform that processes `requirements.txt` for Python packages and `packages.txt` for system dependencies:

*   **`requirements.txt`:** Ensure it includes:
    ```
    selenium
    webdriver-manager
    # opencv-python (and any other necessary Python packages)
    ```
    The platform will install these Python packages. `webdriver-manager` will then handle the `geckodriver` download within the deployment environment.

*   **`packages.txt`:** Ensure it includes system packages required for Firefox and display functionalities:
    ```
    libgl1
    firefox-esr
    ```
    *   `firefox-esr` provides the Firefox browser itself.
    *   `libgl1` is a common graphics library dependency.
    *   Do **not** add `geckodriver` or `firefox-geckodriver` to `packages.txt`, as `webdriver-manager` takes care of providing `geckodriver`.

*   **Functionality:** The platform will automatically install these packages. Firefox will run in headless mode. The manual `geckodriver` download and PATH setup instructions are generally not applicable here.

### Troubleshooting Startup Issues:

*   **Log Files:** The application generates `geckodriver.log` in its working directory. This log is the first place to check for errors related to `geckodriver` and Firefox startup.
    *   For cloud deployments, accessing this log file might vary by platform. Check your platform's documentation for log access.

*   **Common Checks:**
    *   **Local & Cloud:** Ensure `webdriver-manager` can download `geckodriver`. This might require internet access during the first run or in the build process of a deployment.
    *   **Local Development:** If not using `webdriver-manager` (fallback scenario), ensure Firefox is installed and `geckodriver` is manually installed, in PATH, and compatible with your Firefox version.
    *   **Cloud Deployment:**
        *   Verify that `firefox-esr` and `libgl1` (and any other OS dependencies) are correctly listed in `packages.txt` and successfully installed by the platform.
        *   Ensure there are no conflicts with other pre-installed browser or driver versions on the platform if you deviate from the recommended `packages.txt`.

*   **Version Compatibility:** While `webdriver-manager` aims to resolve compatible versions, extreme mismatches between a very old/new Firefox installed manually (local) and the `geckodriver` it picks could still be an issue. Usually, `webdriver-manager` handles this well. For `firefox-esr` from `packages.txt`, it's generally stable.
