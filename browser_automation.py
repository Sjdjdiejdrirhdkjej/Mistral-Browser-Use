import os
import subprocess
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import traceback
from pyvirtualdisplay import Display

class BrowserAutomation:
    def __init__(self):
        self.driver = None
        self.display = None
        self.wait = None
        self.screenshot_counter = 1
        self.element_map = {}  # Maps indexes to elements
        
    def find_firefox_binary(self):
        """Find Firefox binary path using subprocess"""
        possible_paths = [
            '/usr/bin/firefox',
            '/usr/local/bin/firefox',
            '/opt/firefox/firefox',
            '/snap/bin/firefox',
            'firefox'  # In PATH
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run(['which', path], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                continue
        
        # Try using 'which' command
        try:
            result = subprocess.run(['which', 'firefox'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        raise Exception("Firefox binary not found. Please install Firefox.")
    
    def start_browser(self):
        """Start Firefox browser in headless mode with virtual display"""
        print("BROWSER_AUTOMATION: Entered start_browser method.")
        try:
            # Find Firefox binary
            firefox_binary = self.find_firefox_binary()

            # print("Initializing virtual display...")
            # self.display = Display(visible=0, size=(1920, 1080))
            # self.display.start()
            # print("Virtual display started.")

            # try:
            # Setup Firefox options
            options = Options()
            options.binary_location = firefox_binary
            
            # Configure for headless mode
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument('--width=1920')
            options.add_argument('--height=1080')
            options.set_preference('dom.webdriver.enabled', False)
            options.set_preference('useAutomationExtension', False)
            options.set_preference('general.useragent.override', 
                                 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0')
            
            # Create screenshots directory if it doesn't exist
            os.makedirs('screenshots', exist_ok=True)
            
            # Setup Firefox service for geckodriver logging
            # print("Setting up Firefox service for geckodriver logging...")
            # service = Service(log_path=os.path.join(os.getcwd(), 'geckodriver.log'))
            
            # Start the browser
            print("BROWSER_AUTOMATION: Attempting to initialize webdriver.Firefox with basic options.")
            self.driver = webdriver.Firefox(options=options)
            self.wait = WebDriverWait(self.driver, 10)
            
            # Navigate to a default page
            self.driver.get('https://www.google.com')
            time.sleep(2)
            
            print("Firefox browser started successfully (simplified mode)")
            return True
            
            # finally:
            #     if self.driver is None and self.display is not None: # If driver init failed
            #         print("Stopping virtual display due to error in browser start...")
            #         self.display.stop()
            #         self.display = None # Reset display
            
        except Exception as e:
            print(f"Failed to start browser (simplified mode): {str(e)}")
            # Ensure display is stopped if it was started and an outer exception occurs
            # if self.display is not None and self.display.is_started:
            #      print("Stopping virtual display due to outer exception...")
            #      self.display.stop()
            #      self.display = None
            print(traceback.format_exc())
            raise e
    
    def take_screenshot(self):
        """Take a screenshot and save it with a simple name"""
        if not self.driver:
            raise Exception("Browser not started")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{self.screenshot_counter:03d}_{timestamp}.png"
        filepath = os.path.join('screenshots', filename)
        
        self.driver.save_screenshot(filepath)
        self.screenshot_counter += 1
        
        return filepath
    
    def get_interactable_elements(self):
        """Get all interactable elements on the page"""
        if not self.driver:
            raise Exception("Browser not started")
        
        # Selectors for interactable elements
        selectors = [
            'a',  # Links
            'button',  # Buttons
            'input[type="text"]',  # Text inputs
            'input[type="email"]',  # Email inputs
            'input[type="password"]',  # Password inputs
            'input[type="search"]',  # Search inputs
            'input[type="submit"]',  # Submit buttons
            'input[type="button"]',  # Input buttons
            'textarea',  # Text areas
            'select',  # Dropdowns
            '[onclick]',  # Elements with onclick
            '[role="button"]',  # ARIA buttons
            '[tabindex]',  # Focusable elements
            '.btn',  # Bootstrap buttons
            '.button',  # Common button classes
        ]
        
        elements = []
        for selector in selectors:
            try:
                found_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in found_elements:
                    # Check if element is visible and interactable
                    if (element.is_displayed() and 
                        element.is_enabled() and 
                        element.size['height'] > 0 and 
                        element.size['width'] > 0):
                        elements.append(element)
            except:
                continue
        
        # Remove duplicates and sort by position (top-left to bottom-right)
        unique_elements = list(set(elements))
        unique_elements.sort(key=lambda el: (el.location['y'], el.location['x']))
        
        # Create mapping
        self.element_map = {}
        for i, element in enumerate(unique_elements, 1):
            self.element_map[i] = element
        
        return self.element_map
    
    def click_element_by_index(self, index):
        """Click an element by its index"""
        if not self.driver:
            raise Exception("Browser not started")
        
        if index not in self.element_map:
            raise Exception(f"Element with index {index} not found")
        
        element = self.element_map[index]
        
        try:
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            
            # Try regular click first
            element.click()
            
        except Exception as e:
            try:
                # If regular click fails, try JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
            except Exception as js_e:
                try:
                    # If that fails, try ActionChains
                    actions = ActionChains(self.driver)
                    actions.move_to_element(element).click().perform()
                except Exception as ac_e:
                    raise Exception(f"Failed to click element: {str(e)}, JS: {str(js_e)}, AC: {str(ac_e)}")
        
        time.sleep(1)  # Wait for page to respond
    
    def type_text(self, text, element_description):
        """Type text into an element (find by description or use last focused input)"""
        if not self.driver:
            raise Exception("Browser not started")
        
        # Try to find input elements that match the description
        input_selectors = [
            'input[type="text"]',
            'input[type="email"]',
            'input[type="password"]',
            'input[type="search"]',
            'textarea'
        ]
        
        target_element = None
        
        # First, try to find by placeholder, name, or id containing the description
        for selector in input_selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if (element.is_displayed() and element.is_enabled()):
                    placeholder = element.get_attribute('placeholder') or ''
                    name = element.get_attribute('name') or ''
                    id_attr = element.get_attribute('id') or ''
                    
                    if (element_description.lower() in placeholder.lower() or
                        element_description.lower() in name.lower() or
                        element_description.lower() in id_attr.lower()):
                        target_element = element
                        break
            if target_element:
                break
        
        # If not found, use the first visible input field
        if not target_element:
            for selector in input_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        target_element = element
                        break
                if target_element:
                    break
        
        if not target_element:
            raise Exception(f"No suitable input field found for: {element_description}")
        
        # Clear the field and type text
        try:
            target_element.clear()
            target_element.send_keys(text)
            time.sleep(0.5)
        except Exception as e:
            raise Exception(f"Failed to type text: {str(e)}")
    
    def navigate_to(self, url):
        """Navigate to a specific URL"""
        if not self.driver:
            raise Exception("Browser not started")
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        self.driver.get(url)
        time.sleep(3)  # Wait for page to load
    
    def get_page_info(self):
        """Get current page information"""
        if not self.driver:
            raise Exception("Browser not started")
        
        return {
            'title': self.driver.title,
            'url': self.driver.current_url,
            'page_source_length': len(self.driver.page_source)
        }
    
    def close(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.wait = None
            self.element_map = {}
            print("Browser closed")

        # if self.display:
        #     print("Stopping virtual display...")
        #     self.display.stop()
        #     self.display = None
        #     print("Virtual display stopped.")
