# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Setup

1.  **Python:** Ensure you have Python 3.8+ installed.
2.  **Firefox:** This application automates Firefox. Please ensure it is installed on your system.
3.  **Dependencies:** Install the required Python packages. You can install them for your current user by running:
    ```bash
    pip install --user -r requirements.txt
    ```
    Alternatively, if you prefer to install them globally (and have the necessary permissions), you can use:
    ```bash
    pip install -r requirements.txt
    ```
    Ensure that the installation location for Python packages (especially for `streamlit`) is in your system's PATH.
4.  **Geckodriver & Testing:** For detailed instructions on installing `geckodriver` (required for Firefox automation) and for steps to test the application, please see [TESTING.md](TESTING.md).
    *Note: `geckodriver` must be installed manually as per the instructions in `TESTING.md`. It should not be included in `packages.txt` or `requirements.txt`.*
5.  **API Key:** You will need a Mistral AI API key. You can configure this in the application's sidebar or set it as an environment variable `MISTRAL_API_KEY`.
6.  **Running the Application:** Once dependencies are installed, run the application using:
    ```bash
    streamlit run app.py
    ```
