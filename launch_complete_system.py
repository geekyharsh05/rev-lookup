#!/usr/bin/env python3
"""
LinkedIn Profile Extractor - Complete Launcher
Starts persistent session and API server together
"""

import os
import time
import subprocess
import threading
import signal
import sys
from dotenv import load_dotenv

load_dotenv()

class CompleteLauncher:
    def __init__(self):
        self.session_process = None
        self.api_process = None
        self.session_thread = None
        self.running = True
        
    def start_persistent_session_in_thread(self):
        """Start persistent session in a separate thread"""
        try:
            from persistent_session import PersistentOutlookSession
            
            print("🔐 Starting persistent Outlook session...")
            session = PersistentOutlookSession()
            
            if session.start_persistent_session():
                print("✅ Persistent session started successfully!")
                
                # Keep session alive
                while self.running:
                    time.sleep(30)
                    if not session.is_logged_in:
                        print("⚠️  Session lost, attempting restart...")
                        session.login_to_outlook()
                
                session.stop_session()
            else:
                print("❌ Failed to start persistent session")
                
        except Exception as e:
            print(f"❌ Session thread error: {e}")
    
    def start_api_server(self):
        """Start the FastAPI server"""
        try:
            print("🚀 Starting API server...")
            
            # Start API server as subprocess
            cmd = ["uv", "run", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
            self.api_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            print("✅ API server started on http://localhost:8000")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start API server: {e}")
            return False
    
    def start_complete_system(self):
        """Start the complete system"""
        print("🚀 LINKEDIN PROFILE EXTRACTOR - COMPLETE SYSTEM")
        print("=" * 70)
        print()
        print("This will start:")
        print("  1. 🌐 Persistent Outlook browser session")
        print("  2. 🚀 FastAPI server on http://localhost:8000")
        print("  3. 🔄 Automatic session maintenance")
        print("  4. 🔑 Bearer token management")
        print()
        
        try:
            response = input("Start the complete system? (y/n): ").strip().lower()
            
            if response not in ['y', 'yes']:
                print("Cancelled.")
                return False
            
            print("\n" + "=" * 50)
            print("🔧 STEP 1: STARTING PERSISTENT SESSION")
            print("=" * 50)
            
            # Start persistent session in thread
            self.session_thread = threading.Thread(target=self.start_persistent_session_in_thread, daemon=True)
            self.session_thread.start()
            
            # Wait for session to initialize
            print("⏳ Waiting for session to initialize...")
            time.sleep(15)
            
            print("\n" + "=" * 50)
            print("🚀 STEP 2: STARTING API SERVER")
            print("=" * 50)
            
            # Start API server
            if not self.start_api_server():
                return False
            
            # Wait for API server to start
            time.sleep(5)
            
            print("\n" + "=" * 70)
            print("✅ COMPLETE SYSTEM IS RUNNING!")
            print("=" * 70)
            print()
            print("🌐 Persistent Outlook Session: ACTIVE")
            print("🚀 API Server: http://localhost:8000")
            print("📖 API Documentation: http://localhost:8000/docs")
            print()
            print("📡 Available Endpoints:")
            print("   GET  /health                     - Health check")
            print("   GET  /token/status               - Token status")
            print("   GET  /profile/{email}            - Single profile")
            print("   POST /profiles/batch             - Batch profiles")
            print("   GET  /profile/{email}/download   - Download profile")
            print()
            print("💡 Example usage:")
            print("   curl http://localhost:8000/health")
            print("   curl http://localhost:8000/profile/someone@example.com")
            print()
            print("🛑 Press Ctrl+C to stop the complete system")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error starting system: {e}")
            return False
    
    def stop_system(self):
        """Stop the complete system"""
        print("\n🛑 Stopping complete system...")
        
        self.running = False
        
        # Stop API server
        if self.api_process:
            try:
                self.api_process.terminate()
                self.api_process.wait(timeout=10)
                print("✅ API server stopped")
            except Exception as e:
                print(f"⚠️  Error stopping API server: {e}")
                try:
                    self.api_process.kill()
                except:
                    pass
        
        # Stop persistent session
        try:
            from persistent_session import stop_persistent_session
            stop_persistent_session()
            print("✅ Persistent session stopped")
        except Exception as e:
            print(f"⚠️  Error stopping session: {e}")
        
        print("👋 System shutdown complete")
    
    def run_and_wait(self):
        """Run the system and wait for shutdown"""
        if not self.start_complete_system():
            return
        
        try:
            # Wait for user interrupt
            while True:
                time.sleep(1)
                
                # Check if API process is still running
                if self.api_process and self.api_process.poll() is not None:
                    print("❌ API server stopped unexpectedly")
                    break
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_system()

def signal_handler(sig, frame, launcher):
    """Handle Ctrl+C gracefully"""
    launcher.stop_system()
    sys.exit(0)

def main():
    launcher = CompleteLauncher()
    
    # Register signal handler
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, launcher))
    
    launcher.run_and_wait()

if __name__ == "__main__":
    main()
