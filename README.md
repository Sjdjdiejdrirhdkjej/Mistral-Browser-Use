# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Deployment and Dependencies

This application is designed to be run in a Streamlit environment. The necessary dependencies are managed by `requirements.txt` (for Python packages) and `packages.txt` (for system-level packages), with `geckodriver` being handled by a separate script.

**Key Dependencies:**

*   **Python Packages (`requirements.txt`):**
    *   `streamlit`: For running the web application.
    *   `selenium`: For browser automation.
    *   `opencv-python`: For image processing (used by `element_detector.py`).
*   **System Packages (`packages.txt`):**
    *   `firefox-esr` (or `firefox`): The web browser automated by Selenium.
    *   `libgl1`: A common dependency for headless browser operation and GUI libraries.
    *   `xvfb`: X Virtual FrameBuffer, included as a general measure for supporting headless browser operation in diverse environments, even if not always strictly required by modern headless Firefox.
*   **WebDriver:**
    *   `geckodriver`: The WebDriver for Firefox. This is installed via the `setup_geckodriver.sh` script.

**Setup in a Deployment Environment:**

1.  **Install geckodriver:**
    Make the `setup_geckodriver.sh` script executable and run it:
    ```bash
    chmod +x setup_geckodriver.sh
    sudo ./setup_geckodriver.sh
    ```
    This script downloads `geckodriver`, places it in `/usr/local/bin/`, and makes it executable. `/usr/local/bin/` should be in your system's PATH.

2.  **Install System Packages (from `packages.txt`):**
    Ensure your environment can install system packages. For Debian/Ubuntu-based systems, this might involve:
    ```bash
    sudo apt-get update && sudo apt-get install -y $(cat packages.txt)
    ```
    (Note: `packages.txt` now primarily lists Firefox and its dependencies like `libgl1`.)

3.  **Install Python Packages (from `requirements.txt`):**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Streamlit Application:**
    ```bash
    streamlit run app.py
    ```

The `browser_automation.py` script expects `geckodriver` to be accessible via the system's PATH, which is handled by the `setup_geckodriver.sh` script.
