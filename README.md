# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Deployment and Dependencies

This application is designed to be run in a Streamlit environment. The necessary dependencies are managed by `requirements.txt` (for Python packages) and `packages.txt` (for system-level packages).

**Key Dependencies:**

*   **Python Packages (`requirements.txt`):**
    *   `streamlit`: For running the web application.
    *   `selenium`: For browser automation.
    *   `opencv-python`: For image processing (used by `element_detector.py`).
*   **System Packages (`packages.txt`):**
    *   `firefox-esr` (or `firefox`): The web browser automated by Selenium.
    *   `geckodriver`: The WebDriver for Firefox. This must be installed and available in the system's PATH. The application relies on the system's package manager (e.g., `apt` on Debian/Ubuntu) to install `geckodriver` from `packages.txt`.
    *   `libgl1`: A common dependency for headless browser operation.

**Setup in a Deployment Environment:**

1.  Ensure your environment can install system packages. For Debian/Ubuntu-based systems, this might involve:
    ```bash
    sudo apt-get update && sudo apt-get install -y $(cat packages.txt)
    ```
2.  Install Python packages:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the Streamlit application:
    ```bash
    streamlit run app.py
    ```

The `browser_automation.py` script expects `geckodriver` to be accessible via the system's PATH after being installed via `packages.txt`.
