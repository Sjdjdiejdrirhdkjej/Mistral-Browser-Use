# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Local Setup Instructions

These instructions are for setting up the application on your local machine. For deployment to platforms like Streamlit Cloud, see the "Deployment" section below.

1.  **Python:** Ensure you have Python 3.8+ installed.
2.  **Firefox:** This application automates Firefox. Please ensure it is installed on your system.
3.  **Dependencies:** Install the required Python packages. You can install them for your current user byrunning:
    ```bash
    pip install --user -r requirements.txt
    ```
    Alternatively, if you prefer to install them globally (and have the necessary permissions), you can use:
    ```bash
    pip install -r requirements.txt
    ```
    Ensure that the installation location for Python packages (especially for `streamlit`) is in your system's PATH.
4.  **Geckodriver & Testing:** For detailed instructions on installing `geckodriver` (required for Firefox automation) and for steps to test the application, please see [TESTING.md](TESTING.md).
    *Note: `geckodriver` must be installed manually as per the instructions in `TESTING.md`. It should not be included in `packages.txt` or `requirements.txt` for local setup if you're following the manual install guide.*
5.  **API Key:** You will need a Mistral AI API key. You can configure this in the application's sidebar or set it as an environment variable `MISTRAL_API_KEY`.
6.  **Running the Application:** Once dependencies are installed, run the application using:
    ```bash
    streamlit run app.py
    ```

## Deployment (e.g., Streamlit Cloud)

When deploying this application to platforms like Streamlit Cloud:

*   **Headless Mode:** Firefox is automatically configured to run in headless mode, as deployment environments typically do not have a graphical display.
*   **System Dependencies (`packages.txt`):** Ensure your `packages.txt` file includes the following system packages required for Firefox and Selenium:
    ```
    libgl1
    firefox-esr
    geckodriver
    ```
    The platform will attempt to install these using the system package manager (`apt-get`).
*   **Python Dependencies (`requirements.txt`):** Python dependencies are managed by `requirements.txt` as usual. Ensure `selenium` and other necessary packages are listed. `geckodriver` should NOT be listed as a Python package here.

#### Troubleshooting Deployment Issues

If the application crashes during startup in a deployment environment (especially after messages like "spinning up the manager process" or if browser startup fails):

*   **Check Deployment Logs:** Carefully review the logs provided by your deployment platform (e.g., Streamlit Cloud logs). The application has been updated to print detailed error messages during the browser startup phase. Look for lines starting with "!!! ERROR DURING FIREFOX STARTUP !!!" or other error messages printed by `browser_automation.py`. These logs will contain specific error details and tracebacks that are crucial for diagnosing the problem.
*   **Dependencies:** Double-check that `packages.txt` includes `libgl1`, `firefox-esr`, and `geckodriver`, and that `requirements.txt` includes `selenium` and `opencv-python`.
*   **Resource Limits:** Ensure your deployment instance has sufficient memory and CPU resources. Browser startup can be resource-intensive.
