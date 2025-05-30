# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Setup

Before running the application, ensure you have the following prerequisites installed and configured:

### 1. Firefox
Firefox browser must be installed on your system and preferably accessible via the system's PATH. The application will attempt to locate it in common installation directories, but adding it to your PATH is the most reliable method.

### 2. Geckodriver
Geckodriver is a proxy for using W3C WebDriver-compatible clients to interact with Gecko-based browsers like Firefox.

*   **Installation:** Download the appropriate Geckodriver executable for your operating system and Firefox version from the [Mozilla geckodriver releases page](https://github.com/mozilla/geckodriver/releases).
*   **PATH Configuration:** Place the Geckodriver executable in a directory that is part of your system's PATH environment variable. This allows the application to find and use it automatically.

**Troubleshooting Startup Issues:**
The application is configured to use `geckodriver` directly from your system's PATH. If you encounter errors during browser startup (e.g., timeout errors), please verify the following:
*   Both Firefox and Geckodriver are correctly installed.
*   The version of Geckodriver is compatible with your Firefox version.
*   Geckodriver is accessible via the PATH.

The application generates a `geckodriver.log` file in its working directory. This log file can provide valuable diagnostic information if you experience problems with Firefox startup or WebDriver interactions. Check this file for specific error messages from Geckodriver.
