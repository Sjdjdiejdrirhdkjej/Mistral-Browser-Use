import pytest
from unittest.mock import patch, MagicMock
from browser_automation import BrowserAutomation
import os

@pytest.fixture
def browser_instance(mocker):
    # Mock the find_firefox_binary to prevent actual subprocess calls
    mocker.patch('browser_automation.BrowserAutomation.find_firefox_binary', return_value='/usr/bin/firefox')
    browser = BrowserAutomation()
    return browser

def test_browser_automation_initialization(browser_instance):
    assert browser_instance.driver is None
    assert browser_instance.wait is None
    assert browser_instance.screenshot_counter == 1
    assert browser_instance.element_map == {}

@patch('browser_automation.webdriver.Firefox')
def test_start_browser_success(mock_firefox, browser_instance, mocker):
    mock_driver = MagicMock()
    mock_firefox.return_value = mock_driver

    # Mock os.makedirs
    mocker.patch('os.makedirs')

    browser_instance.start_browser()

    mock_firefox.assert_called_once()
    browser_instance.driver.get.assert_called_with('https://www.google.com')
    assert browser_instance.driver is not None
    assert browser_instance.wait is not None
    assert os.makedirs.called # Check if screenshots directory creation was attempted

@patch('browser_automation.webdriver.Firefox')
def test_start_browser_failure(mock_firefox, browser_instance, mocker):
    mock_firefox.side_effect = Exception("Test WebDriverException")
    mocker.patch('os.makedirs')

    with pytest.raises(Exception, match="Test WebDriverException"):
        browser_instance.start_browser()

    assert browser_instance.driver is None

def test_take_screenshot_browser_not_started(browser_instance):
    with pytest.raises(Exception, match="Browser not started"):
        browser_instance.take_screenshot()

@patch('os.makedirs')
@patch('browser_automation.webdriver.Firefox')
def test_take_screenshot_success(mock_firefox, mock_makedirs, browser_instance, mocker):
    # Setup a mock driver
    mock_driver = MagicMock()
    mock_firefox.return_value = mock_driver
    browser_instance.start_browser() # This will set browser_instance.driver

    # Mock the actual save_screenshot method
    mock_driver.save_screenshot = MagicMock()

    # Ensure screenshots directory exists for the test
    # mocker.patch('os.path.exists', return_value=True) # Not needed if os.makedirs is properly mocked

    screenshot_path = browser_instance.take_screenshot()

    mock_driver.save_screenshot.assert_called_once()
    assert screenshot_path.startswith(os.path.join('screenshots', 'screenshot_001_'))
    assert screenshot_path.endswith('.png')
    assert browser_instance.screenshot_counter == 2

def test_close_browser_not_started(browser_instance):
    # Should not raise an error if driver is None
    try:
        browser_instance.close()
    except Exception as e:
        pytest.fail(f"close() raised an exception unexpectedly: {e}")

@patch('browser_automation.webdriver.Firefox')
def test_close_browser_started(mock_firefox, browser_instance, mocker):
    mock_driver = MagicMock()
    mock_firefox.return_value = mock_driver
    mocker.patch('os.makedirs')
    browser_instance.start_browser()

    browser_instance.close()

    mock_driver.quit.assert_called_once()
    assert browser_instance.driver is None
    assert browser_instance.wait is None
    assert browser_instance.element_map == {}
