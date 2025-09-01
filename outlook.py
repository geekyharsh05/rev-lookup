from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import json
import re

options = ChromeOptions()

# Enable logging to capture network requests
options.add_argument("--enable-logging")
options.add_argument("--log-level=0")
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

# OUTLOOK_EMAIL="harshisbest1@outlook.com"
# OUTLOOK_PASSWORD="I9jcdbma9k@"

# Read credentials from environment variables
# Primary: OUTLOOK_EMAIL / OUTLOOK_PASSWORD; Fallback: EMAIL / PASSWORD
OUTLOOK_EMAIL = os.getenv("OUTLOOK_EMAIL") or "harshisbest1@outlook.com"
OUTLOOK_PASSWORD = os.getenv("OUTLOOK_PASSWORD") or "I9jcdbma9k@"

# Persist session data (cookies, storage) by using a dedicated user data directory
profile_dir = os.path.join(os.getcwd(), "chrome_profile")
os.makedirs(profile_dir, exist_ok=True)
options.add_argument(f"--user-data-dir={profile_dir}")

s = Service()  # Chrome will auto-detect the driver
browser = webdriver.Chrome(service=s, options=options)


def wait_for_element(by, value, timeout=10):
    """Wait for an element to be present and return it"""
    try:
        element = WebDriverWait(browser, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        print(f"Timeout waiting for element: {by}={value}")
        return None


def debug_page_elements():
    """Debug function to print all clickable elements on the page"""
    print("=== DEBUG: All clickable elements on page ===")
    try:
        # Find all buttons
        buttons = browser.find_elements(By.TAG_NAME, "button")
        print(f"Found {len(buttons)} buttons:")
        for i, btn in enumerate(buttons):
            try:
                text = btn.text.strip()
                btn_id = btn.get_attribute("id")
                btn_class = btn.get_attribute("class")
                btn_type = btn.get_attribute("type")
                print(f"  Button {i+1}: text='{text}', id='{btn_id}', class='{btn_class}', type='{btn_type}'")
            except:
                print(f"  Button {i+1}: [error reading attributes]")
        
        # Find all inputs
        inputs = browser.find_elements(By.TAG_NAME, "input")
        print(f"Found {len(inputs)} inputs:")
        for i, inp in enumerate(inputs):
            try:
                inp_type = inp.get_attribute("type")
                inp_value = inp.get_attribute("value")
                inp_id = inp.get_attribute("id")
                inp_class = inp.get_attribute("class")
                print(f"  Input {i+1}: type='{inp_type}', value='{inp_value}', id='{inp_id}', class='{inp_class}'")
            except:
                print(f"  Input {i+1}: [error reading attributes]")
        
        # Find all elements with role="button"
        role_buttons = browser.find_elements(By.XPATH, "//*[@role='button']")
        print(f"Found {len(role_buttons)} elements with role='button':")
        for i, elem in enumerate(role_buttons):
            try:
                text = elem.text.strip()
                elem_tag = elem.tag_name
                elem_id = elem.get_attribute("id")
                elem_class = elem.get_attribute("class")
                print(f"  Role button {i+1}: tag='{elem_tag}', text='{text}', id='{elem_id}', class='{elem_class}'")
            except:
                print(f"  Role button {i+1}: [error reading attributes]")
        
        print("=== END DEBUG ===")
    except Exception as e:
        print(f"Error during debug: {e}")

def find_next_button():
    """Find the next button using multiple strategies"""
    print("Searching for next button...")
    
    # Strategy 1: Look for button with "Next" text
    try:
        next_button = WebDriverWait(browser, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]"))
        )
        print("Found next button by text 'Next'")
        return next_button
    except:
        pass
    
    # Strategy 2: Look for input with "Next" value
    try:
        next_button = WebDriverWait(browser, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@value='Next']"))
        )
        print("Found next button by value 'Next'")
        return next_button
    except:
        pass
    
    # Strategy 3: Look for button with "Next" aria-label
    try:
        next_button = WebDriverWait(browser, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Next']"))
        )
        print("Found next button by aria-label 'Next'")
        return next_button
    except:
        pass
    
    # Strategy 4: Look for any button that might be the next button
    try:
        buttons = browser.find_elements(By.TAG_NAME, "button")
        for button in buttons:
            try:
                text = button.text.strip().lower()
                if text in ['next', 'continue', 'sign in', 'submit']:
                    print(f"Found potential next button with text: '{button.text}'")
                    return button
            except:
                continue
    except:
        pass
    
    # Strategy 4.5: Look for any input that might be the next button
    try:
        inputs = browser.find_elements(By.TAG_NAME, "input")
        for input_elem in inputs:
            try:
                value = input_elem.get_attribute("value")
                if value and value.lower() in ['next', 'continue', 'sign in', 'submit']:
                    print(f"Found potential next button with value: '{value}'")
                    return input_elem
            except:
                continue
    except:
        pass
    
    # Strategy 5: Look for submit inputs
    try:
        submit_inputs = browser.find_elements(By.XPATH, "//input[@type='submit']")
        if submit_inputs:
            print(f"Found {len(submit_inputs)} submit inputs")
            return submit_inputs[0]  # Return the first one
    except:
        pass
    
    # Strategy 6: Look for any clickable element that might be the next button
    try:
        # Look for elements with common next button classes or IDs
        selectors = [
            "//button[contains(@class, 'btn')]",
            "//button[contains(@class, 'button')]",
            "//input[contains(@class, 'btn')]",
            "//input[contains(@class, 'button')]",
            "//*[@id='idSIButton9']",  # Old Microsoft ID
            "//*[@id='idSIButton9']",  # Another old Microsoft ID
        ]
        
        for selector in selectors:
            try:
                elements = browser.find_elements(By.XPATH, selector)
                if elements:
                    print(f"Found potential button with selector: {selector}")
                    return elements[0]
            except:
                continue
    except:
        pass
    
    # Strategy 7: Look for buttons by role attribute
    try:
        role_buttons = browser.find_elements(By.XPATH, "//*[@role='button']")
        for button in role_buttons:
            try:
                text = button.text.strip().lower()
                if text in ['next', 'continue', 'sign in', 'submit']:
                    print(f"Found potential next button with role='button' and text: '{button.text}'")
                    return button
            except:
                continue
    except:
        pass
    
    return None


def extract_bearer_token():
    """Extract Bearer token from browser session"""
    try:
        print("Extracting Bearer token...")
        
        # Method 1: Check localStorage
        try:
            local_storage = browser.execute_script("return localStorage;")
            for key, value in local_storage.items():
                if 'token' in key.lower() or 'auth' in key.lower():
                    if isinstance(value, str) and ('Bearer' in value or 'eyJ' in value):
                        print(f"Found token in localStorage['{key}']")
                        return value if value.startswith('Bearer') else f'Bearer {value}'
        except Exception as e:
            print(f"localStorage check failed: {e}")
        
        # Method 2: Check sessionStorage
        try:
            session_storage = browser.execute_script("return sessionStorage;")
            for key, value in session_storage.items():
                if 'token' in key.lower() or 'auth' in key.lower():
                    if isinstance(value, str) and ('Bearer' in value or 'eyJ' in value):
                        print(f"Found token in sessionStorage['{key}']")
                        return value if value.startswith('Bearer') else f'Bearer {value}'
        except Exception as e:
            print(f"sessionStorage check failed: {e}")
        
        # Method 3: Intercept network requests
        try:
            print("Navigating to Outlook to capture network requests...")
            browser.get('https://outlook.live.com/mail/0/')
            time.sleep(5)
            
            # Get browser logs
            logs = browser.get_log('performance')
            for log in logs:
                message = json.loads(log['message'])
                if message['message']['method'] == 'Network.requestWillBeSent':
                    headers = message['message']['params'].get('request', {}).get('headers', {})
                    auth_header = headers.get('Authorization') or headers.get('authorization')
                    if auth_header and auth_header.startswith('Bearer'):
                        print("Found Bearer token in network request")
                        return auth_header
        except Exception as e:
            print(f"Network interception failed: {e}")
        
        # Method 4: Execute script to make a test API call and capture token
        try:
            print("Attempting to capture token from API call...")
            script = """
            // Try to find and return any Bearer token from the page context
            const authToken = window.localStorage.getItem('authToken') || 
                             window.localStorage.getItem('AccessToken') ||
                             window.localStorage.getItem('msal.token') ||
                             window.sessionStorage.getItem('authToken') ||
                             window.sessionStorage.getItem('AccessToken');
            
            if (authToken) {
                return authToken.startsWith('Bearer') ? authToken : 'Bearer ' + authToken;
            }
            
            // Try to extract from any global variables
            if (window.OWA && window.OWA.config && window.OWA.config.authToken) {
                return 'Bearer ' + window.OWA.config.authToken;
            }
            
            return null;
            """
            
            token = browser.execute_script(script)
            if token:
                print("Found token from page context")
                return token
                
        except Exception as e:
            print(f"Script execution failed: {e}")
        
        # Method 5: Make a test request to capture the token
        try:
            print("Making test request to capture authorization header...")
            script = """
            return new Promise((resolve) => {
                const originalFetch = window.fetch;
                let capturedToken = null;
                
                window.fetch = function(...args) {
                    const [url, options] = args;
                    if (options && options.headers && options.headers.authorization) {
                        capturedToken = options.headers.authorization;
                    }
                    return originalFetch.apply(this, args);
                };
                
                // Make a test request
                fetch('/api/v1/me', {
                    headers: {
                        'Accept': 'application/json'
                    }
                }).then(() => {
                    window.fetch = originalFetch;
                    resolve(capturedToken);
                }).catch(() => {
                    window.fetch = originalFetch;
                    resolve(capturedToken);
                });
                
                // Timeout fallback
                setTimeout(() => {
                    window.fetch = originalFetch;
                    resolve(capturedToken);
                }, 5000);
            });
            """
            
            token = browser.execute_async_script(script)
            if token:
                print("Captured token from intercepted request")
                return token
                
        except Exception as e:
            print(f"Request interception failed: {e}")
        
        print("❌ Could not extract Bearer token")
        return None
        
    except Exception as e:
        print(f"Error extracting Bearer token: {e}")
        return None


def login_and_get_token():
    """Login to Outlook and extract Bearer token"""
    token = None
    try:
        browser.get('https://outlook.live.com/owa/logoff.owa')
        browser.get('https://login.live.com/login.srf')
        
        # Wait for page to load and username field to appear
        print("Waiting for login page to load...")
        username = wait_for_element(By.XPATH, "//input[@id='i0116']")
        if not username:
            print("Username field not found. Trying alternative selector...")
            # Try alternative selectors in case Microsoft changed the page
            username = wait_for_element(By.NAME, "loginfmt") or \
                      wait_for_element(By.CSS_SELECTOR, "input[type='email']") or \
                      wait_for_element(By.XPATH, "//input[@type='email']")
        
        if not username:
            raise Exception("Could not find username field")
            
        username.clear()
        if not OUTLOOK_EMAIL:
            raise Exception("Missing environment variable: set OUTLOOK_EMAIL (or EMAIL)")
        username.send_keys(OUTLOOK_EMAIL)
        print("Username entered successfully")

        # Wait a moment for the page to update after entering username
        time.sleep(2)

        # Wait for next button and click it
        print("Looking for next button...")
        next_button = find_next_button()
        
        if not next_button:
            print("Next button not found. Taking screenshot for debugging...")
            # Take a screenshot to help debug
            browser.save_screenshot("login_page_debug.png")
            print("Screenshot saved as 'login_page_debug.png'")
            
            # Debug all page elements
            debug_page_elements()
            
            # Print page source for debugging
            print("Page source preview:")
            print(browser.page_source[:2000])
            
            raise Exception("Could not find next button after trying all strategies")
            
        print(f"Next button found: {next_button.tag_name} - {next_button.text}")
        next_button.click()
        print("Next button clicked")
        time.sleep(3)

        # Wait for password field to appear
        print("Waiting for password field...")
        password = wait_for_element(By.XPATH, "//input[@id='i0118']")
        if not password:
            print("Password field not found. Trying alternative selector...")
            password = wait_for_element(By.NAME, "passwd") or \
                      wait_for_element(By.CSS_SELECTOR, "input[type='password']") or \
                      wait_for_element(By.XPATH, "//input[@type='password']")
        
        if not password:
            raise Exception("Could not find password field")
            
        # Try to enable the password field if needed
        try:
            browser.execute_script("document.getElementById('i0118').setAttribute('class', 'form-control')")
        except:
            pass  # Ignore if this fails
            
        password.clear()
        if not OUTLOOK_PASSWORD:
            raise Exception("Missing environment variable: set OUTLOOK_PASSWORD (or PASSWORD)")
        password.send_keys(OUTLOOK_PASSWORD)
        print("Password entered successfully")

        # Try to enable signin button if needed
        try:
            browser.execute_script("document.getElementById('idSIButton9').disabled=false")
        except:
            pass  # Ignore if this fails
            
        # Wait for and click signin button
        print("Looking for signin button...")
        signin_button = wait_for_element(By.ID, 'idSIButton9')
        if not signin_button:
            print("Signin button not found by ID. Trying alternative selectors...")
            # Try multiple strategies to find the signin button
            signin_button = (
                wait_for_element(By.XPATH, "//input[@type='submit']") or
                wait_for_element(By.CSS_SELECTOR, "input[type='submit']") or
                wait_for_element(By.XPATH, "//button[@type='submit']") or
                wait_for_element(By.XPATH, "//button[contains(text(), 'Sign in')]") or
                wait_for_element(By.XPATH, "//button[contains(text(), 'Sign In')]") or
                wait_for_element(By.XPATH, "//button[contains(text(), 'Signin')]") or
                wait_for_element(By.XPATH, "//input[@value='Sign in']") or
                wait_for_element(By.XPATH, "//input[@value='Sign In']") or
                wait_for_element(By.XPATH, "//button[contains(@aria-label, 'Sign in')]") or
                wait_for_element(By.XPATH, "//button[contains(@aria-label, 'Sign In')]")
            )
        
        if not signin_button:
            print("Signin button not found after trying all strategies. Taking screenshot...")
            browser.save_screenshot("signin_page_debug.png")
            print("Screenshot saved as 'signin_page_debug.png'")
            
            # Debug all page elements
            debug_page_elements()
            
            print("Page source preview:")
            print(browser.page_source[:2000])
            raise Exception("Could not find signin button")
            
        signin_button.click()
        print("Signin button clicked")

        # Wait for and handle the "Stay signed in?" dialog - CLICK YES
        try:
            # Detect the prompt
            prompt = WebDriverWait(browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Stay signed in') or contains(text(), 'Stay signed in?') or contains(text(), 'Keep me signed in')]"))
            )
            # Try common selectors for the YES/primary button
            yes_selectors = [
                (By.ID, 'idSIButton9'),
                (By.CSS_SELECTOR, "button[data-testid='primaryButton']"),
                (By.XPATH, "//button[contains(text(), 'Yes')]")
            ]
            clicked_yes = False
            for by, sel in yes_selectors:
                try:
                    btn = WebDriverWait(browser, 5).until(EC.element_to_be_clickable((by, sel)))
                    btn.click()
                    print("Clicked 'Yes' on Stay signed in prompt")
                    clicked_yes = True
                    break
                except Exception:
                    continue
            if not clicked_yes:
                # Fallback: press Enter which usually activates the primary action (Yes)
                try:
                    browser.switch_to.active_element.send_keys("\n")
                    print("Pressed Enter to confirm 'Yes'")
                except Exception:
                    print("Could not auto-confirm 'Yes'")
        except Exception:
            print("No stay signed in dialog found or already handled")

        # Navigate to inbox and extract token
        print("Navigating to inbox...")
        browser.get(r'https://outlook.live.com/mail/0/')
        
        # Wait for inbox to load
        print("Waiting for inbox to load...")
        time.sleep(10)
        
        # Extract Bearer token
        token = extract_bearer_token()
        
        if token:
            print("✅ Successfully extracted Bearer token!")
            print(f"Token (first 50 chars): {token[:50]}...")
        else:
            print("❌ Failed to extract Bearer token")
        
        return token
        
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return None


def login():
    try:
        browser.get('https://outlook.live.com/owa/logoff.owa')
        browser.get('https://login.live.com/login.srf')
        
        # Wait for page to load and username field to appear
        print("Waiting for login page to load...")
        username = wait_for_element(By.XPATH, "//input[@id='i0116']")
        if not username:
            print("Username field not found. Trying alternative selector...")
            # Try alternative selectors in case Microsoft changed the page
            username = wait_for_element(By.NAME, "loginfmt") or \
                      wait_for_element(By.CSS_SELECTOR, "input[type='email']") or \
                      wait_for_element(By.XPATH, "//input[@type='email']")
        
        if not username:
            raise Exception("Could not find username field")
            
        username.clear()
        if not OUTLOOK_EMAIL:
            raise Exception("Missing environment variable: set OUTLOOK_EMAIL (or EMAIL)")
        username.send_keys(OUTLOOK_EMAIL)
        print("Username entered successfully")

        # Wait a moment for the page to update after entering username
        time.sleep(2)

        # Wait for next button and click it
        print("Looking for next button...")
        next_button = find_next_button()
        
        if not next_button:
            print("Next button not found. Taking screenshot for debugging...")
            # Take a screenshot to help debug
            browser.save_screenshot("login_page_debug.png")
            print("Screenshot saved as 'login_page_debug.png'")
            
            # Debug all page elements
            debug_page_elements()
            
            # Print page source for debugging
            print("Page source preview:")
            print(browser.page_source[:2000])
            
            raise Exception("Could not find next button after trying all strategies")
            
        print(f"Next button found: {next_button.tag_name} - {next_button.text}")
        next_button.click()
        print("Next button clicked")
        time.sleep(3)

        # Wait for password field to appear
        print("Waiting for password field...")
        password = wait_for_element(By.XPATH, "//input[@id='i0118']")
        if not password:
            print("Password field not found. Trying alternative selector...")
            password = wait_for_element(By.NAME, "passwd") or \
                      wait_for_element(By.CSS_SELECTOR, "input[type='password']") or \
                      wait_for_element(By.XPATH, "//input[@type='password']")
        
        if not password:
            raise Exception("Could not find password field")
            
        # Try to enable the password field if needed
        try:
            browser.execute_script("document.getElementById('i0118').setAttribute('class', 'form-control')")
        except:
            pass  # Ignore if this fails
            
        password.clear()
        if not OUTLOOK_PASSWORD:
            raise Exception("Missing environment variable: set OUTLOOK_PASSWORD (or PASSWORD)")
        password.send_keys(OUTLOOK_PASSWORD)
        print("Password entered successfully")

        # Try to enable signin button if needed
        try:
            browser.execute_script("document.getElementById('idSIButton9').disabled=false")
        except:
            pass  # Ignore if this fails
            
        # Wait for and click signin button
        print("Looking for signin button...")
        signin_button = wait_for_element(By.ID, 'idSIButton9')
        if not signin_button:
            print("Signin button not found by ID. Trying alternative selectors...")
            # Try multiple strategies to find the signin button
            signin_button = (
                wait_for_element(By.XPATH, "//input[@type='submit']") or
                wait_for_element(By.CSS_SELECTOR, "input[type='submit']") or
                wait_for_element(By.XPATH, "//button[@type='submit']") or
                wait_for_element(By.XPATH, "//button[contains(text(), 'Sign in')]") or
                wait_for_element(By.XPATH, "//button[contains(text(), 'Sign In')]") or
                wait_for_element(By.XPATH, "//button[contains(text(), 'Signin')]") or
                wait_for_element(By.XPATH, "//input[@value='Sign in']") or
                wait_for_element(By.XPATH, "//input[@value='Sign In']") or
                wait_for_element(By.XPATH, "//button[contains(@aria-label, 'Sign in')]") or
                wait_for_element(By.XPATH, "//button[contains(@aria-label, 'Sign In')]")
            )
        
        if not signin_button:
            print("Signin button not found after trying all strategies. Taking screenshot...")
            browser.save_screenshot("signin_page_debug.png")
            print("Screenshot saved as 'signin_page_debug.png'")
            
            # Debug all page elements
            debug_page_elements()
            
            print("Page source preview:")
            print(browser.page_source[:2000])
            raise Exception("Could not find signin button")
            
        signin_button.click()
        print("Signin button clicked")

        # Wait for and handle the "Stay signed in?" dialog - CLICK YES
        try:
            # Detect the prompt
            prompt = WebDriverWait(browser, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Stay signed in') or contains(text(), 'Stay signed in?') or contains(text(), 'Keep me signed in')]"))
            )
            # Try common selectors for the YES/primary button
            yes_selectors = [
                (By.ID, 'idSIButton9'),
                (By.CSS_SELECTOR, "button[data-testid='primaryButton']"),
                (By.XPATH, "//button[contains(text(), 'Yes')]")
            ]
            clicked_yes = False
            for by, sel in yes_selectors:
                try:
                    btn = WebDriverWait(browser, 5).until(EC.element_to_be_clickable((by, sel)))
                    btn.click()
                    print("Clicked 'Yes' on Stay signed in prompt")
                    clicked_yes = True
                    break
                except Exception:
                    continue
            if not clicked_yes:
                # Fallback: press Enter which usually activates the primary action (Yes)
                try:
                    browser.switch_to.active_element.send_keys("\n")
                    print("Pressed Enter to confirm 'Yes'")
                except Exception:
                    print("Could not auto-confirm 'Yes'")
        except Exception:
            print("No stay signed in dialog found or already handled")

        # Navigate to inbox
        print("Navigating to inbox...")
        browser.get(r'https://outlook.live.com/mail/0/')
        print("Login completed successfully!")

        # Keep the session alive for 30 minutes
        try:
            keep_alive_minutes = 30
            end_time = time.time() + keep_alive_minutes * 60
            print(f"Keeping session alive for {keep_alive_minutes} minutes...")
            while time.time() < end_time:
                try:
                    browser.execute_script("void(0);")
                except Exception:
                    pass
                remaining = int(end_time - time.time())
                mins, secs = divmod(remaining, 60)
                print(f"Session alive - {mins:02d}:{secs:02d} remaining", end='\r')
                time.sleep(30)
            print("\n30-minute session window elapsed.")
        except KeyboardInterrupt:
            print("\nSession keep-alive interrupted by user.")
        
    except Exception as e:
        print(f"Error during login: {str(e)}")
        # Keep browser open for debugging
        input("Press Enter to close browser...")
    finally:
        pass


if __name__ == '__main__':
    login()