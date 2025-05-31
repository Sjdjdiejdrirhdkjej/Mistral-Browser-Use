# Mistral-Browser-Use
Have you always been limited to playwright on your mobile device? Try Mistral Browser Use (MBU) which searches the web using mistral free API at https://console.mistral.ai/

## Browser Automation Setup

This project uses Selenium with Firefox for browser automation. The setup for `geckodriver` (the Firefox WebDriver) is handled as follows:

- **`geckodriver` Installation**:
  - `geckodriver` is NOT listed in `requirements.txt` or `packages.txt` for direct installation by pip or system package managers.
  - Instead, the `setup_geckodriver.py` script automatically downloads the correct version of `geckodriver` for Linux x64 at application startup (`app.py`).
  - It extracts `geckodriver` into a local `bin/` directory within the repository and adds this directory to the system `PATH`.
  - This ensures that Selenium can find and use `geckodriver` without relying on system-wide installations or specific package manager versions, which can be problematic in deployment environments like Streamlit Cloud.
- **Firefox Browser**:
  - The `packages.txt` file should include `firefox-esr` (or a suitable Firefox version) to ensure the browser itself is installed in the Streamlit environment.

This approach provides a more reliable way to manage the `geckodriver` dependency. The `bin/` directory containing the downloaded `geckodriver` is excluded from Git via `.gitignore`.

If you encounter issues with `geckodriver`, check the `setup_geckodriver.py` script and the initial logs from `app.py` for any download or setup errors.
