#!/usr/bin/env python3
"""
Enhanced Token Extraction with Network Request Interception
This script uses Chrome DevTools Protocol to intercept network requests more reliably
"""

import json
import time
import os
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By

def setup_chrome_with_devtools():
    """Setup Chrome with DevTools Protocol enabled for network monitoring"""
    options = ChromeOptions()
    
    # Enable DevTools and performance logging
    options.add_argument("--enable-logging")
    options.add_argument("--log-level=0")
    options.add_argument("--enable-network-service-logging")
    options.add_argument("--remote-debugging-port=9222")
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL', 'browser': 'ALL'})
    
    # Use existing profile
    profile_dir = os.path.join(os.getcwd(), "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    # Disable some features that might interfere
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    return webdriver.Chrome(options=options)

def extract_token_from_existing_session(browser):
    """Extract token from an already logged-in Outlook session"""
    print("🔍 Extracting token from existing Outlook session...")
    
    try:
        # Navigate to Outlook if not already there
        current_url = browser.current_url
        if 'outlook.live.com' not in current_url:
            print("📧 Navigating to Outlook...")
            browser.get('https://outlook.live.com/mail/0/')
            time.sleep(5)
        
        # Method 1: Check for existing tokens in browser storage
        print("📦 Checking browser storage for tokens...")
        storage_script = """
        const tokens = [];
        
        // Check localStorage
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            const value = localStorage.getItem(key);
            if (value && (value.includes('Bearer') || value.includes('eyJ') || key.includes('token') || key.includes('auth'))) {
                tokens.push({type: 'localStorage', key: key, value: value.substring(0, 100)});
                if (value.startsWith('Bearer ') || (value.includes('eyJ') && value.length > 500)) {
                    return value.startsWith('Bearer ') ? value : 'Bearer ' + value;
                }
            }
        }
        
        // Check sessionStorage
        for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            const value = sessionStorage.getItem(key);
            if (value && (value.includes('Bearer') || value.includes('eyJ') || key.includes('token') || key.includes('auth'))) {
                tokens.push({type: 'sessionStorage', key: key, value: value.substring(0, 100)});
                if (value.startsWith('Bearer ') || (value.includes('eyJ') && value.length > 500)) {
                    return value.startsWith('Bearer ') ? value : 'Bearer ' + value;
                }
            }
        }
        
        return null;
        """
        
        storage_token = browser.execute_script(storage_script)
        if storage_token and storage_token != 'null':
            print(f"✅ Found token in browser storage!")
            print(f"   Token: {storage_token[:50]}...")
            return storage_token
        
        # Method 2: Navigate to People/Contacts to trigger LinkedIn requests
        print("👥 Navigating to People section to trigger LinkedIn requests...")
        browser.get('https://outlook.live.com/people/')
        time.sleep(3)
        
        # Clear performance logs first
        try:
            browser.get_log('performance')  # Clear existing logs
        except:
            pass
        
        # Trigger some activity
        try:
            # Click on "New Contact" or search to trigger activity
            new_contact_script = """
            // Look for new contact button or search box
            const newContactBtn = document.querySelector('[data-testid*="new"], button[title*="New"], button[aria-label*="New"]');
            const searchBox = document.querySelector('input[type="search"], input[placeholder*="Search"]');
            
            if (newContactBtn) {
                newContactBtn.click();
                return 'new-contact-clicked';
            } else if (searchBox) {
                searchBox.focus();
                searchBox.value = 'john.doe@example.com';
                searchBox.dispatchEvent(new Event('input', { bubbles: true }));
                return 'search-triggered';
            }
            return 'no-elements-found';
            """
            
            trigger_result = browser.execute_script(new_contact_script)
            print(f"   Activity trigger result: {trigger_result}")
            time.sleep(3)
            
        except Exception as e:
            print(f"   Activity trigger failed: {e}")
        
        # Method 3: Check performance logs for network requests
        print("📊 Checking performance logs for network requests...")
        try:
            logs = browser.get_log('performance')
            print(f"   Found {len(logs)} log entries")
            
            for entry in logs:
                try:
                    log_message = json.loads(entry['message'])
                    message = log_message.get('message', {})
                    
                    if message.get('method') == 'Network.requestWillBeSent':
                        params = message.get('params', {})
                        request = params.get('request', {})
                        url = request.get('url', '')
                        
                        # Look for any Microsoft/Office requests with tokens
                        if any(domain in url for domain in ['loki.delve.office.com', 'graph.microsoft.com', 'login.microsoftonline.com']):
                            headers = request.get('headers', {})
                            auth_header = headers.get('Authorization') or headers.get('authorization')
                            
                            if auth_header and ('Bearer' in auth_header or 'eyJ' in auth_header):
                                print(f"✅ Found Bearer token in network request!")
                                print(f"   URL: {url[:100]}...")
                                print(f"   Token: {auth_header[:50]}...")
                                
                                # Ensure it starts with Bearer
                                if not auth_header.startswith('Bearer'):
                                    auth_header = 'Bearer ' + auth_header
                                
                                return auth_header
                        
                except Exception as log_error:
                    continue
                    
        except Exception as perf_error:
            print(f"   Performance logs error: {perf_error}")
        
        # Method 4: Try to trigger requests by searching for contacts
        print("🔍 Trying contact search to trigger authentication...")
        try:
            browser.get('https://outlook.live.com/people/')
            time.sleep(2)
            
            # Try to use the search functionality
            search_script = """
            const searchInputs = document.querySelectorAll('input[type="search"], input[placeholder*="Search"], input[placeholder*="search"]');
            for (let input of searchInputs) {
                if (input.offsetParent !== null) { // Check if visible
                    input.focus();
                    input.value = 'test@example.com';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                    return 'search-executed';
                }
            }
            return 'no-search-inputs';
            """
            
            search_result = browser.execute_script(search_script)
            print(f"   Search result: {search_result}")
            
            if search_result == 'search-executed':
                time.sleep(5)  # Wait for potential network requests
                
                # Check logs again
                try:
                    logs = browser.get_log('performance')
                    for entry in logs[-20:]:  # Check last 20 entries
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
                                    
                                    if auth_header and 'Bearer' in auth_header:
                                        print(f"✅ Found Bearer token after search!")
                                        print(f"   URL: {url[:100]}...")
                                        print(f"   Token: {auth_header[:50]}...")
                                        return auth_header
                            
                        except Exception:
                            continue
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"   Contact search failed: {e}")
        
        print("❌ Could not extract Bearer token from current session")
        return None
        
    except Exception as e:
        print(f"❌ Error during token extraction: {e}")
        return None

def save_token_to_file(token):
    """Save token to token.txt"""
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

def main():
    """Main function to extract token from existing session"""
    print("🚀 Enhanced Token Extractor")
    print("=" * 50)
    print("This will attempt to extract Bearer token from existing Outlook session")
    print("=" * 50)
    
    browser = None
    try:
        # Setup browser
        browser = setup_chrome_with_devtools()
        
        # Check if already logged in
        browser.get('https://outlook.live.com/mail/0/')
        time.sleep(5)
        
        current_url = browser.current_url
        if 'login' in current_url or 'signin' in current_url:
            print("❌ Not logged in to Outlook. Please log in first using:")
            print("   python outlook.py")
            print("   or")  
            print("   python persistent_session.py")
            return False
        
        print("✅ Found existing Outlook session")
        
        # Extract token
        token = extract_token_from_existing_session(browser)
        
        if token:
            # Save to file
            if save_token_to_file(token):
                print("\n✅ SUCCESS!")
                print(f"Token extracted and saved: {token[:50]}...")
                print("You can now use this token with your API server.")
                return True
            else:
                print("⚠️  Token extracted but failed to save to file")
                print(f"Token: {token}")
                return False
        else:
            print("\n❌ Failed to extract token")
            print("Try these troubleshooting steps:")
            print("1. Make sure you're logged into Outlook")
            print("2. Navigate to People/Contacts section manually")
            print("3. Search for a contact or create a new one")
            print("4. Run this script again")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        if browser:
            try:
                input("Press Enter to close browser...")
                browser.quit()
            except:
                pass

if __name__ == "__main__":
    main()
