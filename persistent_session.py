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
        """Initialize Chrome browser with persistent profile"""
        try:
            print("� Initializing Chrome browser...")
            
            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.profile_path}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            # Remove headless for better debugging
            # options.add_argument("--headless")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            print(f"🔧 Using profile path: {self.profile_path}")
            
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
            return True
            
        except Exception as e:
            print(f"❌ Login failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_bearer_token(self):
        """Extract Bearer token from current session"""
        if not self.browser or not self.is_logged_in:
            print("❌ No active session to extract token from")
            return None
        
        print("🔍 Extracting Bearer token...")
        
        try:
            # Method 1: Try browser storage first
            try:
                script = """
                var token = localStorage.getItem('authToken') || 
                           localStorage.getItem('AccessToken') || 
                           localStorage.getItem('msal.token') ||
                           sessionStorage.getItem('authToken') ||
                           sessionStorage.getItem('AccessToken');
                
                if (token && !token.startsWith('Bearer')) {
                    token = 'Bearer ' + token;
                }
                return token;
                """
                
                stored_token = self.browser.execute_script(script)
                if stored_token and stored_token != 'null':
                    self.last_token = stored_token
                    self.token_timestamp = datetime.now()
                    print(f"✅ Token extracted from storage: {stored_token[:50]}...")
                    return stored_token
            except Exception as e:
                print(f"Storage extraction failed: {e}")
            
            # Method 2: Make a test request to LinkedIn to trigger network activity
            try:
                print("🔄 Making test request to capture fresh token...")
                self.browser.execute_script("""
                fetch('https://www.linkedin.com/voyager/api/me', {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'csrf-token': 'ajax:1234567890'
                    },
                    credentials: 'include'
                }).catch(() => {});
                """)
                
                time.sleep(2)
                
                # Check for performance logs if available
                try:
                    logs = self.browser.get_log('performance')
                    for log in logs:
                        try:
                            message = json.loads(log['message'])
                            if message['message']['method'] == 'Network.requestWillBeSent':
                                headers = message['message']['params'].get('request', {}).get('headers', {})
                                auth_header = headers.get('Authorization') or headers.get('authorization')
                                if auth_header and auth_header.startswith('Bearer'):
                                    self.last_token = auth_header
                                    self.token_timestamp = datetime.now()
                                    print(f"✅ Fresh token captured: {auth_header[:50]}...")
                                    return auth_header
                        except:
                            continue
                except Exception as perf_error:
                    print(f"Performance logs not available: {perf_error}")
                    
            except Exception as e:
                print(f"Test request failed: {e}")
            
            # Method 3: Stay in Outlook and try different extraction approaches
            try:
                print("🔄 Trying additional Outlook-based token extraction...")
                
                # Make sure we're on Outlook
                if 'outlook' not in self.browser.current_url.lower():
                    self.browser.get('https://outlook.live.com/mail/0/')
                    time.sleep(3)
                
                # Try to find tokens in global variables or page context
                outlook_script = """
                // Look for Outlook-specific token storage
                const outlookTokens = [];
                
                // Check for OWA (Outlook Web App) global variables
                if (window.OWA && window.OWA.bootstrap && window.OWA.bootstrap.globals) {
                    const globals = window.OWA.bootstrap.globals;
                    if (globals.authToken) outlookTokens.push('Bearer ' + globals.authToken);
                    if (globals.accessToken) outlookTokens.push('Bearer ' + globals.accessToken);
                }
                
                // Check for Microsoft-specific storage keys
                const msKeys = ['msal.token', 'authToken', 'AccessToken', 'ms-token'];
                msKeys.forEach(key => {
                    const localVal = localStorage.getItem(key);
                    const sessionVal = sessionStorage.getItem(key);
                    if (localVal && (localVal.includes('eyJ') || localVal.startsWith('Bearer'))) {
                        outlookTokens.push(localVal.startsWith('Bearer') ? localVal : 'Bearer ' + localVal);
                    }
                    if (sessionVal && (sessionVal.includes('eyJ') || sessionVal.startsWith('Bearer'))) {
                        outlookTokens.push(sessionVal.startsWith('Bearer') ? sessionVal : 'Bearer ' + sessionVal);
                    }
                });
                
                return outlookTokens.length > 0 ? outlookTokens[0] : null;
                """
                
                outlook_token = self.browser.execute_script(outlook_script)
                if outlook_token:
                    print("✅ Found Outlook token in page context!")
                    return outlook_token
                
            except Exception as e:
                print(f"Outlook token extraction failed: {e}")
            
            print("⚠️  Could not extract fresh token - performance logs not available in this Chrome version")
            print("ℹ️  For Bearer token extraction, need to navigate to LinkedIn and be logged in there")
            return self.last_token
            
        except Exception as e:
            print(f"❌ Token extraction error: {e}")
            return self.last_token
    
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
    
    def keep_session_alive(self):
        """Keep the session alive in a background thread"""
        print("🔄 Starting session keep-alive thread...")
        
        while self.keep_alive and self.browser:
            try:
                if self.is_logged_in:
                    if not self.refresh_session():
                        print("🔄 Session lost, attempting to re-login...")
                        if not self.login_to_outlook():
                            print("❌ Re-login failed")
                            break
                
                # Sleep for 30 seconds before next check
                time.sleep(30)
                
                # Print status
                status = "🟢 ACTIVE" if self.is_logged_in else "🔴 INACTIVE"
                token_age = ""
                if self.token_timestamp:
                    age = datetime.now() - self.token_timestamp
                    token_age = f" | Token age: {age.total_seconds():.0f}s"
                
                print(f"📊 Session Status: {status}{token_age}", end='\r')
                
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
