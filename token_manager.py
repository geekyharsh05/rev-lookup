#!/usr/bin/env python3
"""
Enhanced Token Manager with Automatic Refresh
Handles Bearer token expiration and automatic renewal
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional
import jwt
from persistent_session import get_session_manager

class TokenManager:
    def __init__(self):
        self.token_file = os.path.join(os.getcwd(), "token.txt")
        self.current_token = None
        self.token_expires_at = None
        self.refresh_lock = threading.Lock()
        self.auto_refresh_thread = None
        self.should_run = True
        
        # Load existing token if available
        self.load_token_from_file()
        
    def load_token_from_file(self) -> bool:
        """Load token from file and parse expiration, delete if expired"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token = f.read().strip()
                    
                if token:
                    if self.is_token_valid(token):
                        self.current_token = token
                        self.token_expires_at = self.get_token_expiration(token)
                        print(f"✅ Loaded valid token from file, expires at: {self.token_expires_at}")
                        return True
                    else:
                        # Token is expired or invalid, delete it
                        print("⚠️  Token in file is expired or invalid, removing it...")
                        self.delete_token_file()
                        return False
            return False
        except Exception as e:
            print(f"❌ Error loading token from file: {e}")
            return False
    
    def save_token_to_file(self, token: str) -> bool:
        """Save token to file, always overwriting existing content"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.token_file) if os.path.dirname(self.token_file) else ".", exist_ok=True)
            
            with open(self.token_file, 'w') as f:
                f.write(token)
            print(f"💾 Token saved to {self.token_file}")
            
            # Set file permissions to be readable by owner only for security
            os.chmod(self.token_file, 0o600)
            return True
        except Exception as e:
            print(f"❌ Error saving token to file: {e}")
            return False
    
    def delete_token_file(self) -> bool:
        """Delete the token file"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print(f"🗑️  Deleted expired token file: {self.token_file}")
                self.current_token = None
                self.token_expires_at = None
                return True
            return False
        except Exception as e:
            print(f"❌ Error deleting token file: {e}")
            return False
    
    def is_token_valid(self, token: str) -> bool:
        """Check if token is valid and not expired"""
        try:
            if not token or not token.startswith('Bearer '):
                return False
            
            # Extract JWT part (after 'Bearer ')
            jwt_token = token[7:]
            
            # Decode without verification to get expiration
            decoded = jwt.decode(jwt_token, options={"verify_signature": False})
            exp_timestamp = decoded.get('exp')
            
            if exp_timestamp:
                exp_time = datetime.fromtimestamp(exp_timestamp)
                # Consider token invalid if it expires in less than 10 minutes
                buffer_time = datetime.now() + timedelta(minutes=10)
                return exp_time > buffer_time
            
            return False
            
        except Exception as e:
            print(f"❌ Error validating token: {e}")
            return False
    
    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """Get token expiration time"""
        try:
            if not token or not token.startswith('Bearer '):
                return None
            
            jwt_token = token[7:]
            decoded = jwt.decode(jwt_token, options={"verify_signature": False})
            exp_timestamp = decoded.get('exp')
            
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp)
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting token expiration: {e}")
            return None
    
    def get_fresh_token(self) -> Optional[str]:
        """Get a fresh token, always prioritizing token.txt file"""
        with self.refresh_lock:
            # Always check token.txt first for the most up-to-date token
            print("📄 Checking token.txt for latest token...")
            self.load_token_from_file()
            
            # Check if current token is still valid
            if self.current_token and self.is_token_valid(self.current_token):
                return self.current_token
            
            print("🔄 Current token is expired or invalid, refreshing...")
            return self.refresh_token()
    
    def refresh_token(self) -> Optional[str]:
        """Refresh the Bearer token by re-authenticating"""
        try:
            print("🔄 Starting token refresh process...")
            
            # First check if we already have a valid token in file (maybe updated externally)
            if self.load_token_from_file() and self.current_token:
                print("✅ Found valid token in file during refresh, using it")
                return self.current_token
            
            # Get session manager and extract fresh token
            session_manager = get_session_manager()
            
            # Check if we have an active session with browser
            if session_manager and session_manager.browser and session_manager.is_logged_in:
                print("🔄 Using existing browser session for token extraction...")
                try:
                    fresh_token = session_manager.extract_bearer_token()
                    if fresh_token and self.is_token_valid(fresh_token):
                        print("✅ Extracted fresh token from existing session!")
                        self._save_and_update_token(fresh_token)
                        return fresh_token
                except Exception as e:
                    print(f"⚠️  Failed to extract from existing session: {e}")
            
            # Only start new session if absolutely necessary
            print("🔐 No active session found, checking if we need to start fresh login...")
            print("💡 NOTE: This will open a new browser window for authentication")
            
            # Ask if user wants to proceed (in production, you might want to make this configurable)
            from persistent_session import start_persistent_session
            if not start_persistent_session():
                print("❌ Failed to start persistent session")
                return None
            session_manager = get_session_manager()
            
            # Try to extract token from new session
            fresh_token = session_manager.extract_bearer_token()
            
            if fresh_token and self.is_token_valid(fresh_token):
                # Delete old token first, then save new one
                if os.path.exists(self.token_file):
                    self.delete_token_file()
                
                self.current_token = fresh_token
                self.token_expires_at = self.get_token_expiration(fresh_token)
                
                # Always save to token.txt
                if self.save_token_to_file(fresh_token):
                    print(f"✅ Token refreshed and saved to token.txt successfully!")
                    print(f"🕐 New token expires at: {self.token_expires_at}")
                    return fresh_token
                else:
                    print("⚠️  Token refreshed but failed to save to file")
                    return fresh_token
            else:
                print("❌ Failed to extract valid token from session")
                # Clean up any invalid token in file
                if os.path.exists(self.token_file):
                    self.delete_token_file()
                return None
                
        except Exception as e:
            print(f"❌ Error refreshing token: {e}")
            return None
    
    def start_auto_refresh(self):
        """Start automatic token refresh in background"""
        if self.auto_refresh_thread and self.auto_refresh_thread.is_alive():
            return
        
        self.should_run = True
        self.auto_refresh_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self.auto_refresh_thread.start()
        print("🔄 Started automatic token refresh monitoring")
    
    def stop_auto_refresh(self):
        """Stop automatic token refresh"""
        self.should_run = False
        if self.auto_refresh_thread:
            self.auto_refresh_thread.join(timeout=5)
        print("🛑 Stopped automatic token refresh")
    
    def _auto_refresh_loop(self):
        """Background loop to monitor and refresh tokens"""
        while self.should_run:
            try:
                # Always reload from token.txt to catch external updates
                self.load_token_from_file()
                
                if self.current_token and self.token_expires_at:
                    # Check if token expires in the next 15 minutes
                    time_until_expiry = self.token_expires_at - datetime.now()
                    
                    if time_until_expiry.total_seconds() < 900:  # 15 minutes
                        print("⚠️  Token expires soon, refreshing proactively...")
                        self.refresh_token()
                    elif time_until_expiry.total_seconds() < 0:  # Already expired
                        print("❌ Token has expired, deleting and refreshing...")
                        self.delete_token_file()
                        self.refresh_token()
                else:
                    # No valid token, try to get one
                    print("🔍 No valid token found, attempting to refresh...")
                    self.refresh_token()
                
                # Check every 2 minutes for more responsive monitoring
                time.sleep(120)
                
            except Exception as e:
                print(f"❌ Error in auto-refresh loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def get_token_status(self) -> dict:
        """Get current token status"""
        if not self.current_token:
            return {
                "has_token": False,
                "is_valid": False,
                "expires_at": None,
                "time_until_expiry": None
            }
        
        is_valid = self.is_token_valid(self.current_token)
        time_until_expiry = None
        
        if self.token_expires_at:
            time_until_expiry = self.token_expires_at - datetime.now()
        
        return {
            "has_token": True,
            "is_valid": is_valid,
            "expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "time_until_expiry_seconds": time_until_expiry.total_seconds() if time_until_expiry else None,
            "time_until_expiry_human": str(time_until_expiry).split('.')[0] if time_until_expiry else None,
            "token_preview": self.current_token[:50] + "..." if self.current_token else None
        }

# Global token manager instance
_token_manager = None

def get_token_manager() -> TokenManager:
    """Get or create global token manager"""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
        _token_manager.start_auto_refresh()
    return _token_manager

def get_valid_token() -> Optional[str]:
    """Get a valid Bearer token, refreshing if necessary"""
    manager = get_token_manager()
    return manager.get_fresh_token()

if __name__ == "__main__":
    print("🔑 Token Manager Test")
    print("=" * 50)
    
    manager = TokenManager()
    
    # Show current status
    status = manager.get_token_status()
    print(f"📊 Token Status:")
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # Test getting fresh token
    print("\n🔄 Getting fresh token...")
    token = manager.get_fresh_token()
    
    if token:
        print(f"✅ Token obtained: {token[:50]}...")
        
        # Start auto-refresh
        manager.start_auto_refresh()
        print("\n🔄 Auto-refresh started. Press Ctrl+C to stop...")
        
        try:
            while True:
                time.sleep(30)
                status = manager.get_token_status()
                print(f"📊 Status: Valid={status['is_valid']}, Expires in={status['time_until_expiry_human']}")
        except KeyboardInterrupt:
            manager.stop_auto_refresh()
            print("\n👋 Stopped")
    else:
        print("❌ Failed to get token")
