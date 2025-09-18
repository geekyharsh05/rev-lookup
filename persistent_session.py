#!/usr/bin/env python3
"""
Persistent Browser Session Manager
Keeps browser session alive and extracts Bearer tokens on demand
"""

import os
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

load_dotenv()

class PersistentOutlookSession:
    def __init__(self, email=None, password=None):
        self.browser: Optional[webdriver.Chrome] = None
        self.is_logged_in = False
        self.last_token = None
        self.token_timestamp = None
        self.session_thread = None
        self.keep_alive = True
        
        # Credentials
        self.email = email or os.getenv("OUTLOOK_EMAIL") or "harshisbest1@outlook.com"
        self.password = password or os.getenv("OUTLOOK_PASSWORD") or "I9jcdbma9k@"
        
        # Profile path
        self.profile_path = os.path.join(os.getcwd(), "chrome_profile")
        
    def initialize_browser(self):
        """Initialize Chrome browser with persistent profile and performance logging"""
        try:
            print("🌐 Initializing Chrome browser...")
  
            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.profile_path}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Enable performance logging for token capture
            options.add_argument("--enable-logging")
            options.add_argument("--log-level=0")
            options.add_argument("--enable-network-service-logging")
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            print(f"🔧 Using profile path: {self.profile_path}")
            print("📊 Performance logging enabled for token capture")
            
            # Initialize the driver with a longer timeout
            try:
                self.browser = webdriver.Chrome(options=options)
                print("✅ Chrome driver initialized!")
            except Exception as e:
                print(f"❌ Failed to initialize Chrome driver: {e}")
                raise
            
            # Set timeouts
            self.browser.implicitly_wait(15)
            self.browser.set_page_load_timeout(60)
            
            # Disable automation detection
            self.browser.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Browser ready!")
            return True
            
        except Exception as e:
            print(f"❌ Browser initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def login_to_outlook(self):
        """Perform Outlook login"""
        print("🔐 Logging into Outlook...")
        
        try:
            # Navigate to login
            print("🌐 Navigating to login pages...")
            self.browser.get('https://outlook.live.com/owa/logoff.owa')
            time.sleep(2)
            self.browser.get('https://login.live.com/login.srf')
            time.sleep(5)
            
            print("📧 Looking for email field...")
            # Email field with more flexible selectors
            try:
                email_field = WebDriverWait(self.browser, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='email'] | //input[@name='loginfmt'] | //input[@id='i0116']"))
                )
                print("✅ Found email field!")
            except TimeoutException:
                print("❌ Email field not found, trying alternative approach...")
                # Try to find any input field
                inputs = self.browser.find_elements(By.TAG_NAME, "input")
                email_field = None
                for inp in inputs:
                    inp_type = inp.get_attribute("type")
                    inp_name = inp.get_attribute("name")
                    if inp_type in ["email", "text"] or inp_name == "loginfmt":
                        email_field = inp
                        break
                
                if not email_field:
                    print("❌ Could not find email field")
                    print("Page source preview:")
                    print(self.browser.page_source[:1000])
                    return False
            
            email_field.clear()
            email_field.send_keys(self.email)
            print(f"✅ Email entered: {self.email}")
            
            time.sleep(3)
            
            # Next button with more flexible selectors
            print("🔘 Looking for Next button...")
            try:
                next_button = WebDriverWait(self.browser, 15).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='submit'] | //button[contains(text(),'Next')] | //*[@id='idSIButton9'] | //button[@type='submit']"))
                )
                print("✅ Found Next button!")
            except TimeoutException:
                print("❌ Next button not found, trying alternative approach...")
                # Look for any submit button
                buttons = self.browser.find_elements(By.TAG_NAME, "button")
                inputs = self.browser.find_elements(By.XPATH, "//input[@type='submit']")
                
                next_button = None
                # Try buttons first
                for btn in buttons:
                    text = btn.text.lower()
                    if any(word in text for word in ['next', 'continue', 'sign']):
                        next_button = btn
                        break
                
                # Try submit inputs
                if not next_button and inputs:
                    next_button = inputs[0]
                
                if not next_button:
                    print("❌ Could not find Next button")
                    return False
            
            next_button.click()
            print("✅ Next button clicked!")
            
            time.sleep(5)
            
            # Password field
            print("🔐 Looking for password field...")
            try:
                password_field = WebDriverWait(self.browser, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='password'] | //input[@name='passwd'] | //input[@id='i0118']"))
                )
                print("✅ Found password field!")
            except TimeoutException:
                print("❌ Password field not found")
                print(f"Current URL: {self.browser.current_url}")
                print("Page source preview:")
                print(self.browser.page_source[:1000])
                return False
            
            password_field.clear()
            password_field.send_keys(self.password)
            print("✅ Password entered!")
            
            time.sleep(3)
            
            # Sign in button
            print("🔘 Looking for Sign In button...")
            try:
                signin_button = WebDriverWait(self.browser, 15).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='submit'] | //button[contains(text(),'Sign')] | //*[@id='idSIButton9'] | //button[@type='submit']"))
                )
                print("✅ Found Sign In button!")
            except TimeoutException:
                print("❌ Sign In button not found, trying alternative approach...")
                # Look for any submit button
                buttons = self.browser.find_elements(By.TAG_NAME, "button")
                inputs = self.browser.find_elements(By.XPATH, "//input[@type='submit']")
                
                signin_button = None
                # Try buttons first
                for btn in buttons:
                    text = btn.text.lower()
                    if any(word in text for word in ['sign', 'login', 'submit']):
                        signin_button = btn
                        break
                
                # Try submit inputs
                if not signin_button and inputs:
                    signin_button = inputs[0]
                
                if not signin_button:
                    print("❌ Could not find Sign In button")
                    return False
            
            signin_button.click()
            print("✅ Sign In button clicked!")
            
            time.sleep(8)
            
            # Handle "Stay signed in" prompt
            try:
                print("🔍 Checking for 'Stay signed in' prompt...")
                stay_elements = self.browser.find_elements(By.XPATH, "//*[contains(text(), 'Stay signed in')]")
                if stay_elements:
                    print("✅ Found 'Stay signed in' prompt!")
                    # Look for Yes button
                    yes_buttons = self.browser.find_elements(By.XPATH, "//input[@type='submit'] | //button[contains(text(),'Yes')] | //*[@id='idSIButton9']")
                    if yes_buttons:
                        yes_buttons[0].click()
                        print("✅ Clicked 'Yes' to stay signed in!")
                        time.sleep(3)
                else:
                    print("ℹ️  No 'Stay signed in' prompt found")
            except Exception as e:
                print(f"⚠️  Error handling 'Stay signed in' prompt: {e}")
            
            # Navigate to inbox
            print("📬 Navigating to inbox...")
            self.browser.get('https://outlook.live.com/mail/0/')
            
            # Wait for inbox to load
            print("⏳ Waiting for inbox to load...")
            time.sleep(10)
            
            # Check if we're actually logged in
            current_url = self.browser.current_url
            if 'login' in current_url.lower() or 'signin' in current_url.lower():
                print("❌ Still on login page, authentication may have failed")
                print(f"Current URL: {current_url}")
                return False
            
            self.is_logged_in = True
            print("✅ Successfully logged into Outlook!")
            
            # Extract initial token immediately
            print("🔑 Attempting initial token extraction...")
            initial_token = self.extract_bearer_token()
            
            if initial_token:
                print("✅ Initial token extracted successfully!")
            else:
                print("⚠️  No token found immediately after login - will continue monitoring")
            
            return True
            
        except Exception as e:
            print(f"❌ Login failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_bearer_token(self):
        """Extract Bearer token from current session with loki.delve monitoring"""
        if not self.browser or not self.is_logged_in:
            print("❌ No active session to extract token from")
            return None
        
        print("🔍 Extracting Bearer token with loki.delve monitoring...")
        
        try:
            # Method 1: Check if token.txt already has a valid token
            try:
                token_file = os.path.join(os.getcwd(), "token.txt")
                if os.path.exists(token_file):
                    with open(token_file, 'r') as f:
                        existing_token = f.read().strip()
                    
                    if existing_token and len(existing_token) > 100:
                        print("💾 Found existing token in token.txt")
                        print(f"   Token: {existing_token[:50]}...")
                        self.last_token = existing_token
                        self.token_timestamp = datetime.now()
                        return existing_token
            except Exception:
                pass
            
            # Method 2: Check performance logs for loki.delve requests first
            try:
                print("📊 Monitoring performance logs for loki.delve requests...")
                logs = self.browser.get_log('performance')
                
                for entry in logs[-50:]:  # Check last 50 entries
                    try:
                        log_message = json.loads(entry['message'])
                        message = log_message.get('message', {})
                        
                        if message.get('method') == 'Network.requestWillBeSent':
                            params = message.get('params', {})
                            request = params.get('request', {})
                            url = request.get('url', '')
                            
                            if 'loki.delve.office.com' in url:
                                headers = request.get('headers', {})
                                auth_header = headers.get('Authorization') or headers.get('authorization')
                                
                                if auth_header and auth_header.startswith('Bearer'):
                                    print(f"✅ Found Bearer token in loki.delve request!")
                                    print(f"   URL: {url[:100]}...")
                                    print(f"   Token: {auth_header[:50]}...")
                                    self.last_token = auth_header
                                    self.token_timestamp = datetime.now()
                                    self._save_token_to_file(auth_header)
                                    return auth_header
                                    
                    except Exception:
                        continue
                        
            except Exception as perf_error:
                print(f"Performance logs check failed: {perf_error}")
            
            # Method 3: Check browser storage for authentication tokens
            try:
                print("🔄 Trying browser storage extraction...")
                script = """
                const keys = ['authToken', 'AccessToken', 'msal.token', 'bearerToken', 'ms-token'];
                for (let storage of [localStorage, sessionStorage]) {
                    for (let key of keys) {
                        const value = storage.getItem(key);
                        if (value && (value.includes('eyJ') || value.startsWith('Bearer'))) {
                            return value.startsWith('Bearer') ? value : 'Bearer ' + value;
                        }
                    }
                    
                    // Check all keys for token-like values
                    for (let i = 0; i < storage.length; i++) {
                        const key = storage.key(i);
                        const value = storage.getItem(key);
                        if (key && key.toLowerCase().includes('token') && value && value.length > 500) {
                            if (value.includes('eyJ') || value.startsWith('Bearer')) {
                                return value.startsWith('Bearer') ? value : 'Bearer ' + value;
                            }
                        }
                    }
                }
                return null;
                """
                
                stored_token = self.browser.execute_script(script)
                if stored_token and stored_token != 'null':
                    self.last_token = stored_token
                    self.token_timestamp = datetime.now()
                    self._save_token_to_file(stored_token)
                    print(f"✅ Token extracted from storage: {stored_token[:50]}...")
                    return stored_token
            except Exception as e:
                print(f"Storage extraction failed: {e}")
            
            # Method 4: Navigate to LinkedIn-enabled features in Outlook
            try:
                print("🔄 Navigating to LinkedIn-enabled features in Outlook...")
                
                # Navigate to People/Contacts section which often has LinkedIn integration
                people_urls = [
                    'https://outlook.live.com/people/',
                    'https://outlook.live.com/contacts/',
                    'https://outlook.live.com/mail/0/search'
                ]
                
                for url in people_urls:
                    try:
                        print(f"   Navigating to: {url}")
                        self.browser.get(url)
                        time.sleep(5)
                        
                        # Clear performance logs to get fresh requests
                        try:
                            self.browser.get_log('performance')  # Clear existing logs
                        except:
                            pass
                        
                        # Try to trigger LinkedIn-related activity without complex JavaScript
                        simple_trigger_script = """
                        // Simple triggers that are less likely to fail
                        const searchInputs = document.querySelectorAll('input[type="search"], input[placeholder*="Search"]');
                        if (searchInputs.length > 0) {
                            const input = searchInputs[0];
                            if (input.offsetParent !== null) { // Check if visible
                                input.focus();
                                input.value = 'john.doe@example.com';
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                                return 'search-triggered';
                            }
                        }
                        
                        const buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            const text = btn.textContent.toLowerCase();
                            if ((text.includes('new') || text.includes('contact') || text.includes('person')) && btn.offsetParent !== null) {
                                btn.click();
                                return 'button-clicked';
                            }
                        }
                        
                        return 'no-elements';
                        """
                        
                        trigger_result = self.browser.execute_script(simple_trigger_script)
                        print(f"   Trigger result: {trigger_result}")
                        
                        if trigger_result in ['search-triggered', 'button-clicked']:
                            time.sleep(3)
                            
                            # Check performance logs again after triggering
                            try:
                                logs = self.browser.get_log('performance')
                                print(f"   Found {len(logs)} new log entries after trigger")
                                
                                for entry in logs:
                                    try:
                                        log_message = json.loads(entry['message'])
                                        message = log_message.get('message', {})
                                        
                                        if message.get('method') == 'Network.requestWillBeSent':
                                            params = message.get('params', {})
                                            request = params.get('request', {})
                                            url = request.get('url', '')
                                            
                                            if 'loki.delve.office.com' in url:
                                                headers = request.get('headers', {})
                                                auth_header = headers.get('Authorization') or headers.get('authorization')
                                                
                                                if auth_header and auth_header.startswith('Bearer'):
                                                    print(f"✅ Found Bearer token after triggering LinkedIn features!")
                                                    print(f"   URL: {url[:100]}...")
                                                    print(f"   Token: {auth_header[:50]}...")
                                                    self.last_token = auth_header
                                                    self.token_timestamp = datetime.now()
                                                    self._save_token_to_file(auth_header)
                                                    return auth_header
                                                    
                                    except Exception:
                                        continue
                            except Exception:
                                pass
                        
                    except Exception as nav_error:
                        print(f"   Navigation failed: {nav_error}")
                        continue
                
            except Exception as e:
                print(f"Navigation-based extraction failed: {e}")
            
            # Method 5: Check for authentication in browser context
            try:
                print("🔄 Checking browser's authentication context...")
                
                # Check for authentication cookies and headers
                auth_context_script = """
                // Check cookies for authentication tokens
                const cookies = document.cookie.split(';');
                for (let cookie of cookies) {
                    const [name, value] = cookie.split('=');
                    if (name && (name.includes('authtoken') || name.includes('access_token') || name.includes('Bearer'))) {
                        if (value && (value.includes('Bearer') || value.includes('eyJ'))) {
                            return value.startsWith('Bearer') ? value : 'Bearer ' + value;
                        }
                    }
                }
                
                // Check window objects for authentication
                const authVars = ['authToken', 'accessToken', 'bearerToken', 'token'];
                for (let varName of authVars) {
                    if (window[varName] && typeof window[varName] === 'string' && window[varName].length > 100) {
                        return window[varName].startsWith('Bearer') ? window[varName] : 'Bearer ' + window[varName];
                    }
                }
                
                // Check for Microsoft Graph/Office context
                if (window.Microsoft && window.Microsoft.Graph && window.Microsoft.Graph.token) {
                    return 'Bearer ' + window.Microsoft.Graph.token;
                }
                
                return null;
                """
                
                auth_token = self.browser.execute_script(auth_context_script)
                if auth_token and auth_token != 'null':
                    print("✅ Found authentication token in browser context!")
                    self.last_token = auth_token
                    self.token_timestamp = datetime.now()
                    self._save_token_to_file(auth_token)
                    return auth_token
                
            except Exception as e:
                print(f"Browser context extraction failed: {e}")
            
            print("❌ Could not extract Bearer token from any source")
            print("💡 Try these manual steps:")
            print("   1. Navigate to People/Contacts in Outlook")
            print("   2. Search for a contact or create a new one")
            print("   3. This should trigger LinkedIn profile requests")
            print("   4. Run the token extraction again")
            
            return self.last_token
            
        except Exception as e:
            print(f"❌ Token extraction error: {e}")
            return self.last_token
    
    def _save_token_to_file(self, token):
        """Save token to token.txt file"""
        try:
            token_file = os.path.join(os.getcwd(), "token.txt")
            with open(token_file, 'w') as f:
                f.write(token)
            os.chmod(token_file, 0o600)
            print(f"💾 Token saved to token.txt")
            return True
        except Exception as e:
            print(f"❌ Failed to save token: {e}")
            return False

    def extract_bearer_token_enhanced(self):
        """Enhanced Bearer token extraction from current session with loki.delve monitoring"""
        if not self.browser or not self.is_logged_in:
            print("❌ No active session to extract token from")
            return None
        
        print("🔍 Extracting Bearer token with enhanced loki.delve monitoring...")
        
        try:
            # Method 1: Check performance logs for loki.delve requests
            try:
                print("📊 Monitoring performance logs for loki.delve requests...")
                logs = self.browser.get_log('performance')
                
                for entry in logs[-50:]:  # Check last 50 entries
                    try:
                        log_message = json.loads(entry['message'])
                        message = log_message.get('message', {})
                        
                        if message.get('method') == 'Network.requestWillBeSent':
                            params = message.get('params', {})
                            request = params.get('request', {})
                            url = request.get('url', '')
                            
                            if 'loki.delve.office.com' in url:
                                headers = request.get('headers', {})
                                auth_header = headers.get('Authorization') or headers.get('authorization')
                                
                                if auth_header and auth_header.startswith('Bearer'):
                                    print(f"✅ Found Bearer token in loki.delve request!")
                                    self.last_token = auth_header
                                    self.token_timestamp = datetime.now()
                                    self._save_token_to_file(auth_header)
                                    return auth_header
                                    
                    except Exception:
                        continue
                        
            except Exception as perf_error:
                print(f"Performance logs check failed: {perf_error}")
            
            # Method 2: Trigger a loki.delve request to capture token
            try:
                print("🔄 Triggering loki.delve request to capture fresh token...")
                
                capture_script = """
                return new Promise((resolve) => {
                    let capturedToken = null;
                    
                    const originalFetch = window.fetch;
                    window.fetch = function(url, options) {
                        if (url.includes('loki.delve.office.com') && options && options.headers) {
                            const authHeader = options.headers.authorization || options.headers.Authorization;
                            if (authHeader && authHeader.startsWith('Bearer')) {
                                capturedToken = authHeader;
                            }
                        }
                        return originalFetch.apply(this, arguments);
                    };
                    
                    // Test request to capture token
                    const testEmail = 'test@example.com';
                    const encodedEmail = testEmail.replace('@', '%40');
                    const correlationId = Math.random().toString(36).substring(2, 15);
                    
                    const testUrl = `https://nam.loki.delve.office.com/api/v2/linkedin/profiles?smtp=${encodedEmail}&personaType=User&displayName=${encodedEmail}&RootCorrelationId=${correlationId}&CorrelationId=${correlationId}&ClientCorrelationId=${correlationId}&ConvertGetPost=true`;
                    
                    fetch(testUrl, {
                        method: 'POST',
                        headers: {
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'X-ClientType': 'OneOutlook',
                            'X-ClientFeature': 'LivePersonaCard'
                        },
                        body: JSON.stringify({})
                    }).finally(() => {
                        window.fetch = originalFetch;
                        resolve(capturedToken);
                    });
                    
                    setTimeout(() => {
                        window.fetch = originalFetch;
                        resolve(capturedToken);
                    }, 8000);
                });
                """
                
                fresh_token = self.browser.execute_async_script(capture_script)
                if fresh_token:
                    print(f"✅ Captured fresh Bearer token!")
                    self.last_token = fresh_token
                    self.token_timestamp = datetime.now()
                    self._save_token_to_file(fresh_token)
                    return fresh_token
                    
            except Exception as script_error:
                print(f"Script capture failed: {script_error}")
            
            # Method 3: Fallback to original method
            print("🔄 Falling back to original extraction method...")
            return self.extract_bearer_token()
            
        except Exception as e:
            print(f"❌ Enhanced token extraction error: {e}")
            return self.extract_bearer_token()
    
    def refresh_session(self):
        """Refresh the session to keep it alive"""
        if not self.browser or not self.is_logged_in:
            return False
        
        try:
            # Keep session alive by interacting with the page
            self.browser.execute_script("void(0);")
            
            # Check if we're still logged in
            current_url = self.browser.current_url
            if 'login' in current_url or 'signin' in current_url:
                print("⚠️  Session expired, need to re-login")
                self.is_logged_in = False
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Session refresh failed: {e}")
            return False
    
    def monitor_loki_requests(self):
        """Continuously monitor for loki.delve requests and extract tokens"""
        print("🔍 Starting loki.delve request monitoring...")
        
        while self.keep_alive and self.browser and self.is_logged_in:
            try:
                # Check performance logs every 10 seconds
                time.sleep(10)
                
                try:
                    logs = self.browser.get_log('performance')
                    
                    for entry in logs[-10:]:  # Check last 10 entries
                        try:
                            log_message = json.loads(entry['message'])
                            message = log_message.get('message', {})
                            
                            if message.get('method') == 'Network.requestWillBeSent':
                                params = message.get('params', {})
                                request = params.get('request', {})
                                url = request.get('url', '')
                                
                                if 'loki.delve.office.com' in url:
                                    headers = request.get('headers', {})
                                    auth_header = headers.get('Authorization') or headers.get('authorization')
                                    
                                    if auth_header and auth_header.startswith('Bearer'):
                                        print(f"\n🎉 NEW TOKEN CAPTURED from loki.delve!")
                                        print(f"   URL: {url[:100]}...")
                                        print(f"   Token: {auth_header[:50]}...")
                                        self.last_token = auth_header
                                        self.token_timestamp = datetime.now()
                                        self._save_token_to_file(auth_header)
                                        
                        except Exception:
                            continue
                            
                except Exception as perf_error:
                    # Performance logs might not be available, continue monitoring
                    pass
                
                # Print monitoring status
                token_age = ""
                if self.token_timestamp:
                    age = datetime.now() - self.token_timestamp
                    token_age = f" | Last token: {age.total_seconds():.0f}s ago"
                
                print(f"🔍 Monitoring loki.delve requests...{token_age}", end='\r')
                
            except Exception as e:
                print(f"\n❌ Monitor error: {e}")
                time.sleep(5)
    
    def keep_session_alive(self):
        """Keep the session alive in a background thread with token monitoring"""
        print("🔄 Starting session keep-alive and token monitoring...")
        
        # Start loki monitoring in a separate thread
        monitor_thread = threading.Thread(target=self.monitor_loki_requests, daemon=True)
        monitor_thread.start()
        
        while self.keep_alive and self.browser:
            try:
                if self.is_logged_in:
                    if not self.refresh_session():
                        print("🔄 Session lost, attempting to re-login...")
                        if not self.login_to_outlook():
                            print("❌ Re-login failed")
                            break
                    
                    # Check for fresh tokens every 5 minutes
                    if self.token_timestamp:
                        age = datetime.now() - self.token_timestamp
                        if age.total_seconds() > 300:  # 5 minutes
                            print("\n🔄 Token is old, extracting fresh token...")
                            fresh_token = self.extract_bearer_token()
                            if fresh_token:
                                print("✅ Fresh token extracted!")
                
                # Sleep for 30 seconds before next check
                time.sleep(30)
                
                # Print status
                status = "🟢 ACTIVE" if self.is_logged_in else "🔴 INACTIVE"
                token_age = ""
                if self.token_timestamp:
                    age = datetime.now() - self.token_timestamp
                    token_age = f" | Token age: {age.total_seconds():.0f}s"
                
                print(f"\n📊 Session Status: {status}{token_age}")
                
            except Exception as e:
                print(f"\n❌ Keep-alive error: {e}")
                time.sleep(10)
    
    def start_persistent_session(self):
        """Start the persistent session"""
        print(" Starting persistent Outlook session...")
        
        # Setup browser
        if not self.initialize_browser():
            return False
        
        # Login
        if not self.login_to_outlook():
            return False
        
        # Extract initial token
        self.extract_bearer_token()
        
        # Start keep-alive thread
        self.session_thread = threading.Thread(target=self.keep_session_alive, daemon=True)
        self.session_thread.start()
        
        print("✅ Persistent session started!")
        print("🌐 Browser window will remain open")
        print("🔄 Session will be automatically maintained")
        print("🔑 Bearer tokens will be refreshed as needed")
        
        return True
    
    def get_current_token(self):
        """Get the current Bearer token"""
        if not self.is_logged_in:
            return None
        
        # If token is older than 10 minutes, try to get a fresh one
        if self.token_timestamp and datetime.now() - self.token_timestamp > timedelta(minutes=10):
            print("🔄 Token is old, extracting fresh token...")
            fresh_token = self.extract_bearer_token()
            if fresh_token:
                return fresh_token
        
        return self.last_token
    
    def stop_session(self):
        """Stop the persistent session"""
        print("🛑 Stopping persistent session...")
        
        self.keep_alive = False
        
        if self.browser:
            try:
                self.browser.quit()
            except:
                pass
        
        print("✅ Session stopped")

# Global session manager
session_manager = None

def get_session_manager():
    """Get or create the global session manager"""
    global session_manager
    
    if session_manager is None:
        session_manager = PersistentOutlookSession()
    
    return session_manager

def start_persistent_session():
    """Start the persistent session"""
    manager = get_session_manager()
    return manager.start_persistent_session()

def get_bearer_token():
    """Get current Bearer token from persistent session"""
    manager = get_session_manager()
    return manager.get_current_token()

def stop_persistent_session():
    """Stop the persistent session"""
    global session_manager
    
    if session_manager:
        session_manager.stop_session()
        session_manager = None

if __name__ == "__main__":
    print("🚀 Persistent Outlook Session Manager")
    print("=" * 50)
    
    manager = PersistentOutlookSession()
    
    try:
        if manager.start_persistent_session():
            print("\n✅ Persistent session is running!")
            print("Press Ctrl+C to stop...")
            
            # Keep main thread alive
            while True:
                time.sleep(60)
                token = manager.get_current_token()
                if token:
                    print(f"\n🔑 Current token: {token[:50]}...")
                else:
                    print("\n⚠️  No token available")
                    
    except KeyboardInterrupt:
        print("\n👋 Stopping session...")
        manager.stop_session()
