# Mistral-Browser-Use (Now with Local Transformers)
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using AI. This project now primarily uses a local, CPU-based model from Xenova/Transformers.js for core decision-making and can also connect to Mistral AI's API.

## Setup

Before running the application, ensure you have the following prerequisites installed and configured:

### 1. Python Environment
Ensure you have Python installed. This project uses a `requirements.txt` file to manage Python dependencies. It's recommended to use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```
This will install all necessary packages, including `streamlit`, `selenium`, `webdriver-manager`, and `transformers`.

### 2. AI Backend

This project uses two main AI provider options:

*   **Xenova T5-Small (Local Default):**
    *   The application leverages the `transformers` library to run a `t5-small` model variant (`XFTransformations/gte-small`) locally on your CPU. This model is used for tasks like generating step-by-step plans from your objectives and making decisions during automation.
    *   **No separate installation is required** beyond the Python dependencies in `requirements.txt`. The model will be downloaded automatically by the `transformers` library on its first use.
    *   This allows the core functionality to run without needing external API keys or a dedicated GPU.

*   **Mistral AI (Optional):**
    *   You can optionally configure the application to use Mistral AI's API for potentially more powerful models.
    *   To use Mistral AI, you will need an API key from [Mistral AI](https://console.mistral.ai/).
    *   The API key can be entered in the application's sidebar or set as an environment variable (`MISTRAL_API_KEY`).

The AI provider can be selected from the application's sidebar.

### 3. Firefox Browser

*   **Local Development:**
    Firefox browser must be installed on your system. The application will attempt to locate it in common installation directories. If not found, ensure Firefox is in your system's PATH or provide the correct binary location if you modify the script.
*   **Cloud Deployments (e.g., Streamlit Cloud):**
    Firefox (specifically `firefox-esr`) is installed via the `packages.txt` file. See the deployment notes below.

### 4. Geckodriver (for Firefox Automation)

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
    transformers
    # opencv-python (and any other necessary Python packages)
    ```
    The platform will install these Python packages. `webdriver-manager` will then handle the `geckodriver` download, and `transformers` will handle the local model download within the deployment environment.

*   **`packages.txt`:** Ensure it includes system packages required for Firefox and display functionalities:
    ```
    libgl1
    firefox-esr
    ```
    *   `firefox-esr` provides the Firefox browser itself.
    *   `libgl1` is a common graphics library dependency.
    *   Do **not** add `geckodriver` or `firefox-geckodriver` to `packages.txt`, as `webdriver-manager` takes care of providing `geckodriver`.

*   **Functionality:** The platform will automatically install these packages. Firefox will run in headless mode. The manual `geckodriver` download and PATH setup instructions are generally not applicable here. The `transformers` library will download the `XFTransformations/gte-small` model to the deployment's file system on first use. Ensure the platform provides sufficient disk space for the model cache (typically a few hundred MBs).

### Troubleshooting Startup Issues:

*   **Log Files:** The application generates `geckodriver.log` in its working directory. This log is the first place to check for errors related to `geckodriver` and Firefox startup. Model download issues from `transformers` might appear in the Streamlit application logs.
    *   For cloud deployments, accessing these log files might vary by platform. Check your platform's documentation for log access.

*   **Common Checks:**
    *   **Local & Cloud:** Ensure `webdriver-manager` can download `geckodriver` and `transformers` can download its models. This might require internet access during the first run or in the build process of a deployment.
    *   **Local Development:** If not using `webdriver-manager` (fallback scenario), ensure Firefox is installed and `geckodriver` is manually installed, in PATH, and compatible with your Firefox version.
    *   **Cloud Deployment:**
        *   Verify that `firefox-esr` and `libgl1` (and any other OS dependencies) are correctly listed in `packages.txt` and successfully installed by the platform.
        *   Ensure there are no conflicts with other pre-installed browser or driver versions on the platform if you deviate from the recommended `packages.txt`.
        *   Check platform limits on disk space if model downloads appear to fail.

*   **Version Compatibility:** While `webdriver-manager` aims to resolve compatible versions, extreme mismatches between a very old/new Firefox installed manually (local) and the `geckodriver` it picks could still be an issue. Usually, `webdriver-manager` handles this well. For `firefox-esr` from `packages.txt`, it's generally stable.
