# Manual Test Plan

This document outlines the manual testing steps to verify recent changes related to navigation and real-time UI updates.

## 1. Setup

1.  **Install Dependencies:**
    *   Ensure you have Python installed.
    *   Open your terminal and navigate to the root of this repository.
    *   Install the required Python packages using the `requirements.txt` file:
        ```bash
        pip install -r requirements.txt
        ```

### Installing geckodriver (for Firefox browser automation)

If `geckodriver` is not found by the system (e.g., you see an error like "Unable to locate package geckodriver" or "geckodriver executable needs to be in PATH"), you'll need to install it manually:

1.  **Go to the geckodriver releases page:**
    [https://github.com/mozilla/geckodriver/releases](https://github.com/mozilla/geckodriver/releases)

2.  **Download the latest version for your system.** Look for files like:
    *   `geckodriver-vX.YY.Z-linux64.tar.gz` for 64-bit Linux.
    *   `geckodriver-vX.YY.Z-linux32.tar.gz` for 32-bit Linux.
    *   (Adjust for macOS or Windows if providing instructions for them, but prioritize Linux based on the user's error).

3.  **Extract the downloaded file.** For example, if you downloaded `geckodriver-v0.36.0-linux64.tar.gz`:
    ```bash
    tar -xvzf geckodriver-v0.36.0-linux64.tar.gz
    ```

4.  **Make it executable:**
    ```bash
    chmod +x geckodriver
    ```

5.  **Move the `geckodriver` executable to a directory in your system's PATH.** A common location is `/usr/local/bin`:
    ```bash
    sudo mv geckodriver /usr/local/bin/
    ```

6.  **Verify the installation:**
    ```bash
    geckodriver --version
    ```
    This should output the version of geckodriver if it's installed correctly.

2.  **Run the Streamlit Application:**
    *   In your terminal, from the root of the repository, run:
        ```bash
        streamlit run app.py
        ```
    *   This should open the "Web Automation Assistant" in your web browser.

3.  **Set Mistral API Key:**
    *   In the application's sidebar, under "🔧 Configuration" -> "Mistral AI API Key", enter your valid Mistral AI API key.
    *   A "✅ API Key configured" message should appear if the key is accepted.

## 2. Testing Navigation Fix (Issue 1)

This section tests if the browser correctly navigates based on user commands.

*   **Steps:**
    1.  In the application UI, click the "🚀 Start Browser" button in the sidebar. Wait for the "✅ Browser started" message.
    2.  In the chat input field, type the objective: `Go to wikipedia.org` and press Enter.
    3.  **Observe:** The browser window controlled by the application should navigate to `https://www.wikipedia.org`. The chat should display messages indicating the thinking process and the action `navigate('https://www.wikipedia.org')` (or similar).
    4.  Once the previous step is complete and the browser is on Wikipedia, type a new objective in the chat input: `Type bbc.com into the browser address bar` and press Enter.
    5.  **Observe:** The browser window should navigate to `https://www.bbc.com`. The chat should display messages indicating the thinking process and the action `type('bbc.com', into='browser address bar')` followed by a navigation message.

*   **Expected Outcome:**
    *   The browser successfully navigates to the specified URLs in both test cases.
    *   Chat messages clearly indicate the navigation actions being performed (e.g., "Navigating to https://www.wikipedia.org", "Navigating to bbc.com").

## 3. Testing Real-time UI Updates (Issue 2)

This section tests if the UI updates promptly during multi-step automation.

*   **Steps:**
    1.  Ensure the browser is started (if not, click "🚀 Start Browser").
    2.  In the chat input field, type an objective that requires multiple steps, for example: `Go to google.com, search for "latest tech news", and then click on the first search result.` Press Enter.
    3.  **Observe:** Carefully watch the chat UI as the automation proceeds.

*   **Expected Outcome:**
    *   Messages such as "--- Step X ---", "🤔 **Thinking:** ...", "⚡ **Action:** ...", screenshots of the page, and annotated screenshots with element indexes should appear in the chat UI sequentially and promptly as each part of the automation task is executed.
    *   The updates should not appear all at once only after the entire automation is complete. There should be a clear, step-by-step flow of information in the chat.

## 4. General Checks

*   **Error Monitoring:**
    *   Throughout all tests, keep an eye on the terminal where you launched `streamlit run app.py`. Ensure no new Python tracebacks or error messages appear.
    *   Similarly, monitor the Streamlit UI for any error messages or unexpected behavior (e.g., red error boxes).
*   **Core Functionality:**
    *   Verify that the screenshot functionality (`Current page screenshot`) still works and displays the current view of the automated browser.
    *   Verify that element detection (`Elements detected and indexed`) still highlights elements on the screenshot correctly.

If all tests pass and expected outcomes are observed, the recent changes are considered verified.
