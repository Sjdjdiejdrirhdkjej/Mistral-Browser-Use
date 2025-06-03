# Web Automation Assistant (with Local AI and OCR)

This Streamlit application enables web automation driven by AI. It can understand user objectives, interact with web pages, and make decisions based on page content. The primary AI for decision-making is a locally run T5-small model, which interprets on-screen text extracted via OCR. Optionally, it can connect to Mistral AI's API for access to more powerful models.

## Core Functionality

*   **Web Interaction:** Uses Selenium to control a Firefox browser.
*   **Element Detection:** Can identify interactive elements on a webpage.
*   **AI-Powered Decision Making:**
    *   **Local Default (Xenova T5-Small + OCR):** Uses the `XFTransformations/gte-small` model (a T5-small variant) running locally via the `transformers` library. To understand on-screen content, it employs Optical Character Recognition (OCR) powered by `pytesseract` (which uses the Tesseract OCR engine) to extract text from screenshots. This text is then fed to the T5 model for analysis and action planning.
    *   **Mistral AI (Optional):** Can use Mistral AI's multimodal models if configured with an API key, allowing for direct image analysis.
*   **Task Planning:** Breaks down user objectives into step-by-step tasks.
*   **E2B Desktop Mode:** Optionally allows control over a sandboxed E2B desktop environment.

## Setup

Before running the application, ensure you have the following prerequisites installed and configured:

### 1. Python Environment
Ensure you have Python 3.9+ installed. This project uses a `requirements.txt` file to manage Python dependencies. It's recommended to use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```
This will install all necessary Python packages, including `streamlit`, `selenium`, `webdriver-manager`, `transformers`, `Pillow`, and `pytesseract`.

### 2. Tesseract OCR Engine
For the local AI (Xenova T5-Small) to understand on-screen content, Tesseract OCR must be installed on your system as `pytesseract` relies on it.

*   **Installation:** Follow the official installation instructions for your operating system: [https://github.com/tesseract-ocr/tesseract#installing-tesseract](https://github.com/tesseract-ocr/tesseract#installing-tesseract)
    *   On Debian/Ubuntu: `sudo apt-get install tesseract-ocr`
    *   On macOS: `brew install tesseract`
    *   On Windows: Download the installer from the official Tesseract at UB Mannheim page.
*   **PATH:** Ensure the Tesseract executable is in your system's PATH after installation. `pytesseract` will try to find it, but if it reports `TesseractNotFoundError`, it means the executable was not found.

### 3. AI Backend Configuration

As mentioned, the project supports two main AI provider options, selectable from the application's sidebar:

*   **Xenova T5-Small (Local Default):**
    *   Leverages the `transformers` library for the `XFTransformations/gte-small` model (local, CPU-based).
    *   Uses OCR (Tesseract via `pytesseract`) for visual understanding.
    *   The T5 model is downloaded automatically by the `transformers` library on first use.
    *   Requires Tesseract OCR engine to be installed (see step 2).

*   **Mistral AI (Optional):**
    *   To use Mistral AI, you need an API key from [Mistral AI](https://console.mistral.ai/).
    *   Enter the API key in the application's sidebar or set it as an environment variable (`MISTRAL_API_KEY`). This provider uses Mistral's multimodal models and does not rely on local OCR.

### 4. Firefox Browser

*   **Local Development:** Firefox browser must be installed.
*   **Cloud Deployments (e.g., Streamlit Cloud):** Firefox (specifically `firefox-esr`) is typically installed via the `packages.txt` file (see deployment notes).

### 5. Geckodriver (for Firefox Automation)

`webdriver-manager` (listed in `requirements.txt`) automatically downloads and manages Geckodriver. No manual setup is usually needed.

The application runs Firefox in **headless mode** by default.

## Note for Streamlit Cloud Deployments

*   **`requirements.txt`:** Should include `streamlit`, `selenium`, `webdriver-manager`, `transformers`, `Pillow`, `pytesseract`.
*   **`packages.txt`:** For system dependencies on Streamlit Cloud:
    ```
    libgl1
    firefox-esr
    tesseract-ocr # For OCR functionality
    # language packs for tesseract if needed, e.g., tesseract-ocr-eng
    ```
    *   `tesseract-ocr` is crucial for the default Xenova T5-Small provider.
*   **Functionality:** The `transformers` library will download the T5 model on first use. Ensure sufficient disk space.

## Troubleshooting Startup Issues

*   **OCR Errors (`TesseractNotFoundError`):** This means `pytesseract` cannot find the Tesseract OCR engine. Ensure Tesseract is correctly installed and its executable is in your system's PATH. For cloud deployments, ensure `tesseract-ocr` is in `packages.txt`.
*   **Log Files:** Check `geckodriver.log` for browser automation issues. Streamlit application logs may show model download or OCR errors.
*   **Common Checks:**
    *   Internet access for first-time model/driver downloads.
    *   Correct versions and paths for Firefox/Geckodriver if not using `webdriver-manager`.
    *   Cloud deployment: `packages.txt` correctness, disk space for models.
*   **Version Compatibility:** Generally handled by `webdriver-manager`. `firefox-esr` is usually stable.
---

This README provides a comprehensive overview of the project, its setup, and how the different AI backends (especially the local T5+OCR approach) function.
