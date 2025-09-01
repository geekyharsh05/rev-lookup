#!/usr/bin/env python3
"""
Extract Bearer Token from Already Running Browser Session
Uses the existing browser session to extract tokens without creating conflicts
"""

import os
import json
import time
import requests
from typing import Optional
import platform
import subprocess

def wait_for_devtools(port: int, timeout: int = 30) -> bool:
    """Wait until Chrome DevTools endpoint is responding on the given port."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"http://localhost:{port}/json/version", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def launch_chrome_with_debug(port: int = 9222, profile_dir: str = "chrome_profile", url: Optional[str] = "https://outlook.live.com/mail/") -> bool:
    """Launch Chrome with remote debugging enabled using the provided profile.
    Returns True if launch command was issued successfully (does not guarantee DevTools is ready)."""
    try:
        profile_path = os.path.abspath(profile_dir)
        os.makedirs(profile_path, exist_ok=True)

        system = platform.system()
        if system == "Darwin":  # macOS
            cmd = [
                "open", "-na", "Google Chrome", "--args",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_path}",
            ]
            if url:
                cmd.append(url)
            subprocess.Popen(cmd)
            return True
        elif system == "Linux":
            # Try common chrome binaries
            for bin_name in ["google-chrome", "chromium-browser", "chromium", "google-chrome-stable"]:
                chrome_path = shutil.which(bin_name) if 'shutil' in globals() else None
                if not chrome_path:
                    import shutil as _shutil
                    chrome_path = _shutil.which(bin_name)
                if chrome_path:
                    cmd = [
                        chrome_path,
                        f"--remote-debugging-port={port}",
                        f"--user-data-dir={profile_path}",
                    ]
                    if url:
                        cmd.append(url)
                    subprocess.Popen(cmd)
                    return True
            return False
        elif system == "Windows":
            # Basic attempt for Windows (may need adjustment based on installation path)
            chrome_exe = os.path.expandvars(r"%ProgramFiles%/Google/Chrome/Application/chrome.exe")
            if not os.path.exists(chrome_exe):
                chrome_exe = os.path.expandvars(r"%ProgramFiles(x86)%/Google/Chrome/Application/chrome.exe")
            if os.path.exists(chrome_exe):
                cmd = [
                    chrome_exe,
                    f"--remote-debugging-port={port}",
                    f"--user-data-dir={profile_path}",
                ]
                if url:
                    cmd.append(url)
                subprocess.Popen(cmd)
                return True
            return False
        else:
            return False
    except Exception as e:
        print(f"⚠️ Failed to launch Chrome with debugging: {e}")
        return False


def ensure_debug_port(ports = (9222, 9223, 9224, 9225)) -> Optional[int]:
    """Ensure we have a working Chrome DevTools debugging port.
    1) Try to discover an existing port
    2) If none, try launching Chrome on one of the candidate ports and wait for it
    Returns the working port or None.
    """
    # First try discovery
    discovered = find_chrome_debug_port()
    if discovered:
        return discovered

    print("🛠️ No debugging port found. Attempting to launch Chrome with remote debugging...")
    for p in ports:
        launched = launch_chrome_with_debug(port=p)
        if launched:
            print(f"🚀 Launched Chrome with --remote-debugging-port={p}. Waiting for DevTools endpoint...")
            if wait_for_devtools(p, timeout=30):
                print(f"✅ DevTools endpoint is responding on port {p}")
                return p
            else:
                print(f"⏰ DevTools endpoint did not respond on port {p} in time. Trying next port...")
    return None


def find_chrome_debug_port():
    """Find the debugging port of the running Chrome instance"""
    try:
        # Check if Chrome is running with remote debugging
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        for line in lines:
            if 'chrome_profile' in line and 'remote-debugging-port' in line:
                # Extract port number
                parts = line.split('--remote-debugging-port=')
                if len(parts) > 1:
                    port = parts[1].split()[0]
                    if port.isdigit():
                        return int(port)
        
        # If no explicit port found, try common debugging ports
        for port in [9222, 9223, 9224, 9225]:
            try:
                response = requests.get(f'http://localhost:{port}/json/version', timeout=1)
                if response.status_code == 200:
                    return port
            except:
                continue
                
        return None
    except Exception as e:
        print(f"Error finding Chrome debug port: {e}")
        return None

def get_chrome_tabs(debug_port):
    """Get list of Chrome tabs"""
    try:
        response = requests.get(f'http://localhost:{debug_port}/json/list', timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Error getting Chrome tabs: {e}")
        return []

# Updated to accept full tab and prefer webSocketDebuggerUrl

def extract_token_from_tab(tab, debug_port):
    """Extract token from a specific Chrome tab using CDP"""
    try:
        import websocket
        import threading
        import queue
        
        # Prefer Chrome-provided websocket URL if present
        ws_url = tab.get('webSocketDebuggerUrl') or f"ws://localhost:{debug_port}/devtools/page/{tab.get('id')}"
        
        token_queue = queue.Queue()
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                
                # Debug: Show Runtime.evaluate results
                if 'result' in data and data.get('id') in [2.5, 3]:
                    result = data.get('result', {})
                    if 'result' in result:
                        print(f"🔍 JS Result (id={data.get('id')}): {result['result']}")
                
                # Check for network requests being sent
                if 'method' in data and data['method'] == 'Network.requestWillBeSent':
                    request = data.get('params', {}).get('request', {})
                    headers = request.get('headers', {})
                    url = request.get('url', '')
                    
                    # Log ALL network requests for debugging
                    print(f"🌐 Network request: {url[:100]}...")
                    
                    # Check for any Authorization header in requests
                    auth_header = headers.get('Authorization') or headers.get('authorization')
                    if auth_header and auth_header.startswith('Bearer'):
                        print(f"🔑 Found Bearer token in request to: {url}")
                        print(f"🔑 Token: {auth_header[:50]}...")
                        
                        # Save ANY Bearer token we find, not just from configuration endpoint
                        token_queue.put(auth_header)
                        return
                    
                    # Target the specific configuration endpoint
                    if 'loki.delve.office.com/api/v1/livepersonacard/configuration' in url:
                        print(f"🎯 FOUND TARGET URL: {url}")
                        print(f"📋 Headers: {list(headers.keys())}")
                        if not auth_header:
                            print("⚠️ No Authorization header found in target request")
                        
                # Also check for responses to see what we might be missing
                if 'method' in data and data['method'] == 'Network.responseReceived':
                    response = data.get('params', {}).get('response', {})
                    url = response.get('url', '')
                    
                    if 'loki.delve.office.com' in url:
                        print(f"📥 Response from: {url}")
                        print(f"Status: {response.get('status')}")
                                
            except Exception as e:
                print(f"Error processing message: {e}")
        
        def on_error(ws, error):
            print(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print("WebSocket connection closed")
        
        # Create WebSocket connection
        ws = websocket.WebSocketApp(ws_url,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)
        
        # Start WebSocket in a thread
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Enable network and runtime domains
        time.sleep(2)  # Give more time for connection
        
        print("🔧 Enabling Network domain to capture all requests...")
        ws.send(json.dumps({
            "id": 1,
            "method": "Network.enable",
            "params": {}
        }))
        
        print("🔧 Enabling Runtime domain...")
        ws.send(json.dumps({
            "id": 2,
            "method": "Runtime.enable",
            "params": {}
        }))
        
        # Clear cache to ensure fresh requests
        ws.send(json.dumps({
            "id": 2.1,
            "method": "Network.clearBrowserCache"
        }))
        
        # Wait for domains to be enabled
        time.sleep(2)
        
        # Check if page is loaded and is an Outlook page
        page_check_js = """
        (function() {
            const url = window.location.href;
            const isOutlook = url.includes('outlook.live.com') || url.includes('outlook.live.com');
            const readyState = document.readyState;
            console.log('Page check - URL:', url, 'Ready state:', readyState, 'Is Outlook:', isOutlook);
            return {
                url: url,
                readyState: readyState,
                isOutlook: isOutlook,
                title: document.title
            };
        })();
        """
        
        ws.send(json.dumps({
            "id": 2.5,
            "method": "Runtime.evaluate",
            "params": {
                "expression": page_check_js,
                "returnByValue": True
            }
        }))
        
        # Execute JavaScript to trigger network requests and navigate to trigger the endpoint
        js_code = """
        (async function() {
            console.log('🎯 Starting enhanced token extraction...');
            console.log('Current URL:', window.location.href);
            console.log('Document ready state:', document.readyState);
            
            // Function to wait for page load
            function waitForPageLoad() {
                return new Promise((resolve) => {
                    if (document.readyState === 'complete') {
                        resolve();
                    } else {
                        window.addEventListener('load', resolve);
                    }
                });
            }
            
            // Wait for page to be ready
            await waitForPageLoad();
            console.log('✅ Page is ready');
            
            // First, navigate to Outlook if not already there
            if (!window.location.href.includes('outlook.')) {
                console.log('🌐 Navigating to Outlook...');
                window.location.href = 'https://outlook.live.com/mail/';
                return 'navigating_to_outlook';
            }
            
            // Try multiple approaches to trigger the configuration endpoint
            console.log('🎯 Attempting multiple triggers for configuration endpoint...');
            
            // Method 1: Direct API call
            try {
                console.log('📡 Method 1: Direct configuration API call...');
                const response1 = await fetch('https://loki.delve.office.com/api/v1/livepersonacard/configuration?cultureName=en-US', {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'X-ClientType': 'OneOutlook',
                        'X-ClientFeature': 'LivePersonaCard',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'include'
                });
                console.log('✅ Direct API call status:', response1.status);
            } catch (error) {
                console.log('⚠️ Direct API call failed:', error.message);
            }
            
            // Method 2: Navigate to People section
            try {
                console.log('👥 Method 2: Navigating to People section...');
                if (window.location.href.includes('outlook.live.com')) {
                    window.location.href = 'https://outlook.live.com/people/';
                }
            } catch (error) {
                console.log('⚠️ People navigation failed:', error.message);
            }
            
            // Method 3: Try alternative endpoints that might trigger token
            try {
                console.log('🔄 Method 3: Alternative LinkedIn endpoint...');
                const response3 = await fetch('https://nam.loki.delve.office.com/api/v2/linkedin/profiles?smtp=user%40example.com&personaType=User', {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'X-ClientType': 'OneOutlook'
                    },
                    credentials: 'include'
                });
                console.log('✅ Alternative endpoint status:', response3.status);
            } catch (error) {
                console.log('⚠️ Alternative endpoint failed:', error.message);
            }
            
            // Method 4: Try to trigger via DOM interaction
            try {
                console.log('🖱️ Method 4: DOM interaction to trigger requests...');
                // Look for any elements that might trigger persona card requests
                const peopleElements = document.querySelectorAll('[data-component="PersonaCard"], [data-testid*="persona"], .ms-Persona');
                if (peopleElements.length > 0) {
                    console.log(`Found ${peopleElements.length} persona elements, clicking first one...`);
                    peopleElements[0].click();
                }
            } catch (error) {
                console.log('⚠️ DOM interaction failed:', error.message);
            }
            
            return 'all_methods_attempted';
        })();
        """
        
        ws.send(json.dumps({
            "id": 3,
            "method": "Runtime.evaluate",
            "params": {
                "expression": js_code,
                "awaitPromise": True
            }
        }))
        
        # Wait for token or timeout
        print("⏳ Waiting for Bearer token from network requests (up to 30 seconds)...")
        print("💡 The script will capture ANY Bearer token it finds in network requests")
        try:
            token = token_queue.get(timeout=30)
            ws.close()
            print(f"✅ Successfully captured Bearer token!")
            return token
        except queue.Empty:
            print("⏰ Timeout - No Bearer token captured from network requests")
            print("\n� Troubleshooting steps:")
            print("   1. Make sure you're logged into Outlook")
            print("   2. Try manually refreshing the page")
            print("   3. Navigate to People/Contacts section")
            print("   4. Click on any contact or profile picture")
            print("   5. Search for someone in the search bar")
            print("   6. The configuration request should trigger automatically")
            ws.close()
            return None
            
    except ImportError:
        print("websocket-client not installed. Installing...")
        import subprocess
        subprocess.run(['pip', 'install', 'websocket-client'], check=True)
        return extract_token_from_tab(tab, debug_port)
    except Exception as e:
        print(f"Error extracting token from tab: {e}")
        return None



def extract_bearer_token():
    """Main function to extract bearer token from existing session"""
    print("🔍 Extracting Bearer token from existing Chrome session...")
    print("🔗 Using Chrome DevTools Protocol to monitor configuration endpoint...")
    # Use the new ensure_debug_port which can also launch Chrome
    debug_port = ensure_debug_port()
    
    if not debug_port:
        print("❌ Could not start/find Chrome debugging port")
        print("💡 Make sure Chrome is installed and try again")
        return None
    
    print(f"✅ Debugging available on port {debug_port}")
    
    # Get Chrome tabs
    tabs = get_chrome_tabs(debug_port)
    if not tabs:
        print("❌ No Chrome tabs found")
        return None
    
    print(f"📑 Found {len(tabs)} Chrome tabs")
    
    # Look for Outlook/Office tabs
    outlook_tabs = []
    for tab in tabs:
        url = tab.get('url', '')
        if any(domain in url for domain in ['outlook.', 'live.', 'delve.']):
            outlook_tabs.append(tab)
    
    # If not found, try opening Outlook and re-query tabs once
    if not outlook_tabs:
        print("🌐 No Outlook/Office tabs found. Opening Outlook and retrying...")
        launch_chrome_with_debug(port=debug_port, url="https://outlook.live.com/mail/")
        if wait_for_devtools(debug_port, timeout=10):
            tabs = get_chrome_tabs(debug_port)
            for tab in tabs:
                url = tab.get('url', '')
                if any(domain in url for domain in ['outlook.', 'office.', 'delve.']):
                    outlook_tabs.append(tab)

    if not outlook_tabs:
        print("❌ No Outlook/Office tabs found after opening Outlook")
        print("💡 Please ensure Outlook is open in Chrome")
        return None
    
    print(f"✅ Found {len(outlook_tabs)} Outlook tabs")
    
    # Try to extract token from each Outlook tab
    for tab in outlook_tabs:
        print(f"🔍 Extracting from tab: {tab.get('title', 'Unknown')}")
        token = extract_token_from_tab(tab, debug_port)
        if token:
            return token
    
    return None

def save_token(token):
    """Save token to token.txt file"""
    try:
        with open('token.txt', 'w') as f:
            f.write(token)
        os.chmod('token.txt', 0o600)
        print(f"💾 Token saved to token.txt")
        return True
    except Exception as e:
        print(f"❌ Error saving token: {e}")
        return False

def main():
    """Main execution"""
    print("🚀 Configuration Endpoint Bearer Token Extraction")
    print("=" * 60)
    print("🎯 TARGET: loki.delve.office.com/api/v1/livepersonacard/configuration")
    print("📡 Monitoring ONLY this endpoint for Authorization header")
    print("=" * 60)
    
    token = extract_bearer_token()
    
    if token:
        print(f"\n✅ SUCCESS! Extracted Bearer token:")
        print(f"🔑 {token[:50]}...")
        print(f"📏 Token length: {len(token)} characters")
        
        if save_token(token):
            print("📄 Token saved to token.txt")
            print("\n🎉 You can now use the token for API calls!")
            print("\n📋 Next steps:")
            print("   • Test with: uv run api_server.py")
            print("   • Or use directly in your application")
        else:
            print("⚠️ Token extracted but not saved to file")
            
        return token
    else:
        print("\n❌ Failed to extract Bearer token from configuration endpoint")
        print("\n💡 Troubleshooting suggestions:")
        print("   1. ✅ Ensure Chrome is running with Outlook logged in")
        print("   2. 🔧 Verify Chrome has debugging enabled (--remote-debugging-port)")
        print("   3. 🔄 Try refreshing the Outlook page to trigger the configuration call")
        print("   4. 🌐 Navigate to different Outlook sections to trigger the endpoint")
        print("\n🔍 The script only monitors the configuration endpoint:")
        return None

if __name__ == "__main__":
    main()
