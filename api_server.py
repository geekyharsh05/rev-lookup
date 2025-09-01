from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import asyncio
import aiohttp
import json
import os
import uuid
from typing import Dict
from datetime import datetime
import threading
from persistent_session import get_session_manager, start_persistent_session, get_bearer_token
from token_manager import get_token_manager, get_valid_token
import tempfile

app = FastAPI(
    title="LinkedIn Profile Extractor API",
    description="API to extract LinkedIn profiles using Outlook Bearer tokens",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to store session state
session_started: bool = False
startup_lock = threading.Lock()

class LinkedInProfileExtractor:
    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        
    def encode_email(self, email: str) -> str:
        return email.replace('@', '%40')
    
    def generate_correlation_id(self) -> str:
        return str(uuid.uuid4())
    
    async def fetch_linkedin_profile(self, email: str) -> Dict:
        """Fetch LinkedIn profile data for a given email""" 
        encoded_email = self.encode_email(email)
        root_correlation_id = self.generate_correlation_id()
        correlation_id = self.generate_correlation_id()
        client_correlation_id = self.generate_correlation_id()
        
        url = f"https://nam.loki.delve.office.com/api/v2/linkedin/profiles?smtp={encoded_email}&personaType=User&displayName={encoded_email}&RootCorrelationId={root_correlation_id}&CorrelationId={correlation_id}&ClientCorrelationId={client_correlation_id}&ConvertGetPost=true%20"
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-ClientType': 'OneOutlook',
            'X-ClientFeature': 'LivePersonaCard',
            'X-ClientArchitectureVersion': 'v2',
            'X-ClientScenario': 'LinkedInProfileSearchResult',
            'X-HostAppApp': 'Mail',
            'X-HostAppPlatform': 'Web',
            'X-LPCVersion': '1.20250703.7.0',
            'authorization': self.auth_token,
            'X-HostAppRing': 'WW',
            'X-HostAppVersion': '20250704003.08',
            'X-HostAppCapabilities': '{"isLokiContactDataDisabled":false,"isOnePersonViewEnabled":false,"isOnePersonContextualViewEnabled":false,"isMsalAuthEnabled":true}',
            'X-AccountLinkedIn3S': 'false',
            'X-Client-Language': 'en-US'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={}) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"LinkedIn API error: {response.status} - {await response.text()}"
                    )
                
                return await response.json()

async def ensure_session_started():
    """Ensure the persistent session is started"""
    global session_started
    
    if not session_started:
        with startup_lock:
            if not session_started:  # Double-check locking
                print("🚀 Starting persistent Outlook session...")
                
                # Run session startup in thread executor
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, start_persistent_session)
                
                if success:
                    session_started = True
                    print("✅ Persistent session started successfully!")
                else:
                    raise HTTPException(status_code=503, detail="Failed to start persistent session")
    
    return True

async def get_fresh_token() -> str:
    """Get a fresh Bearer token - simple logic: use token.txt if exists, extract if not"""
    try:
        print("📄 Getting token for API request...")
        
        # Step 1: Check if token.txt exists and has content
        token_file = os.path.join(os.getcwd(), "token.txt")
        
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    token = f.read().strip()
                
                if token:
                    print(f"✅ Using token from token.txt: {token[:50]}...")
                    return token
                else:
                    print("⚠️  token.txt exists but is empty")
            except Exception as e:
                print(f"⚠️  Error reading token.txt: {e}")
        else:
            print("ℹ️  token.txt file does not exist")
        
        # Step 2: No token in file, try to extract from existing session
        session_manager = get_session_manager()
        if session_manager and session_manager.browser and session_manager.is_logged_in:
            print("🔄 No token file, trying to extract from existing browser session...")
            try:
                fresh_token = session_manager.extract_bearer_token()
                if fresh_token:
                    # Save to token.txt for future use
                    with open(token_file, 'w') as f:
                        f.write(fresh_token)
                    os.chmod(token_file, 0o600)
                    print(f"✅ Extracted and saved token to token.txt: {fresh_token[:50]}...")
                    return fresh_token
            except Exception as e:
                print(f"⚠️  Failed to extract from existing session: {e}")
        
        # Step 3: No token and no session - clear instructions
        print("❌ No token.txt file and no active browser session")
        
        raise HTTPException(
            status_code=401, 
            detail="No Bearer token found. Please create token.txt file or extract a fresh token."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting token: {e}")
        raise HTTPException(status_code=500, detail=f"Token retrieval error: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "LinkedIn Profile Extractor API",
        "version": "1.0.0",
        "endpoints": {
            "GET /profile/{email}": "Get LinkedIn profile for email",
            "POST /profile": "Get LinkedIn profile for single email (body: {email: 'user@example.com'})",
            "POST /profiles/batch": "Get LinkedIn profiles for multiple emails (body: {emails: [...], delay_seconds: 2})",
            "POST /profiles/batch/enhanced": "Enhanced batch processing with progress tracking",
            "POST /profile/download": "Download single LinkedIn profile (body: {email: 'user@example.com'})",
            "POST /profiles/batch/download": "Download multiple LinkedIn profiles (body: {emails: [...], delay_seconds: 2})",
            "GET /health": "Health check",
            "GET /token/status": "Check token status",
            "POST /token/refresh": "Force token refresh (may open browser)",
            "POST /token/manual": "Manually upload Bearer token (body: {token: 'Bearer xyz...'})"
        }
    }

@app.get("/health")
async def health_check():
    manager = get_session_manager()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "session_started": session_started,
        "session_active": manager.is_logged_in if manager else False,
        "token_available": get_bearer_token() is not None
    }

@app.get("/token/status")
async def token_status():
    """Enhanced token status with automatic refresh monitoring"""
    # Get status from both session manager and token manager
    session_manager = get_session_manager()
    token_manager = get_token_manager()
    
    session_status = {
        "session_started": session_started,
        "session_active": session_manager.is_logged_in if session_manager else False,
        "session_token_timestamp": session_manager.token_timestamp.isoformat() if session_manager and session_manager.token_timestamp else None,
    }
    
    token_status = token_manager.get_token_status()
    
    return {
        **session_status,
        **token_status,
        "auto_refresh_active": token_manager.auto_refresh_thread.is_alive() if token_manager.auto_refresh_thread else False
    }

@app.post("/token/refresh")
async def force_token_refresh():
    """Force a token refresh (may open browser window)"""
    try:
        token_manager = get_token_manager()
        fresh_token = token_manager.refresh_token()
        
        if fresh_token:
            return {
                "success": True,
                "message": "Token refreshed successfully",
                "token_preview": fresh_token[:50] + "...",
                "expires_at": token_manager.token_expires_at.isoformat() if token_manager.token_expires_at else None
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to refresh token")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")

@app.post("/token/manual")
async def manual_token_upload(request: dict):
    """Manually upload a Bearer token"""
    try:
        token = request.get("token", "").strip()
        
        if not token:
            raise HTTPException(status_code=400, detail="Token is required in request body")
        
        # Ensure token starts with Bearer
        if not token.startswith("Bearer "):
            token = "Bearer " + token
        
        # Basic format validation only
        if not token.startswith("Bearer ") or len(token) < 50:
            raise HTTPException(status_code=400, detail="Token format appears invalid (should start with 'Bearer ' and be reasonably long)")
        
        # Accept any token that looks like a Bearer token
        print(f"✅ Accepting token for manual upload: {token[:50]}...")
        
        # Save token
        token_manager = get_token_manager()
        if token_manager.save_token_to_file(token):
            token_manager.current_token = token
            token_manager.token_expires_at = token_manager.get_token_expiration(token)
            
            return {
                "success": True,
                "message": "Token uploaded and saved successfully",
                "token_preview": token[:50] + "...",
                "expires_at": token_manager.token_expires_at.isoformat() if token_manager.token_expires_at else None
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save token to file")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual token upload failed: {str(e)}")

@app.get("/profile/{email}")
async def get_linkedin_profile(email: str):
    """Get LinkedIn profile for a single email"""
    try:
        # Get fresh token
        token = await get_fresh_token()
        
        # Create extractor and fetch profile
        extractor = LinkedInProfileExtractor(token)
        profile_data = await extractor.fetch_linkedin_profile(email)
        
        return {
            "success": True,
            "email": email,
            "data": profile_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")

@app.post("/profiles/batch")
async def get_linkedin_profiles_batch(request: dict):
    """Get LinkedIn profiles for multiple emails"""
    try:
        # Extract emails and delay from request body
        emails = request.get("emails", [])
        delay_seconds = request.get("delay_seconds", 2)
        
        if not emails:
            raise HTTPException(status_code=400, detail="emails array is required in request body")
        
        # if len(emails) > 50:
        #     raise HTTPException(status_code=400, detail="Maximum 50 emails allowed per batch")
        
        # Get fresh token
        token = await get_fresh_token()
        
        extractor = LinkedInProfileExtractor(token)
        results = []
        errors = []
        
        for i, email in enumerate(emails):
            try:
                print(f"Processing {i + 1}/{len(emails)}: {email}")
                
                profile_data = await extractor.fetch_linkedin_profile(email)
                
                results.append({
                    "email": email,
                    "success": True,
                    "data": profile_data,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Add delay between requests (except for the last one)
                if i < len(emails) - 1:
                    await asyncio.sleep(delay_seconds)
                
                # Longer delay every 10 profiles
                if (i + 1) % 10 == 0 and i + 1 < len(emails):
                    print(f"Taking 10 second break after {i + 1} profiles...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                error_msg = str(e)
                print(f"Error processing {email}: {error_msg}")
                
                errors.append({
                    "email": email,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Stop on error
                print("Stopping batch process due to error")
                break
        
        return {
            "success": True,
            "total_emails": len(emails),
            "processed": len(results),
            "errors": len(errors),
            "results": results,
            "errors_details": errors,
            "completed_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing error: {str(e)}")

@app.post("/profiles/batch/enhanced")
async def get_linkedin_profiles_batch_enhanced(request: dict):
    """Enhanced batch processing with JavaScript-style logic and progress tracking"""
    try:
        # Extract configuration from request
        emails = request.get("emails", [])
        delay_seconds = request.get("delay_seconds", 2)
        stop_on_error = request.get("stop_on_error", True)
        save_individual_files = request.get("save_individual_files", False)
        long_break_interval = request.get("long_break_interval", 10)  # Every N profiles
        long_break_duration = request.get("long_break_duration", 10)  # Seconds
        
        if not emails:
            raise HTTPException(status_code=400, detail="emails array is required in request body")
        
        if len(emails) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 emails allowed per enhanced batch")
        
        print(f"🚀 Starting enhanced batch processing for {len(emails)} emails")
        print(f"⚙️  Config: delay={delay_seconds}s, stop_on_error={stop_on_error}, long_break_every={long_break_interval}")
        
        # Get fresh token with automatic refresh
        token = await get_fresh_token()
        extractor = LinkedInProfileExtractor(token)
        
        # Results tracking
        results = []
        errors = []
        start_time = datetime.now()
        
        # Process each email
        for i, email in enumerate(emails):
            current_progress = {
                "current_index": i,
                "current_email": email,
                "total_emails": len(emails),
                "processed": len(results),
                "errors": len(errors),
                "progress_percentage": round((i / len(emails)) * 100, 2)
            }
            
            try:
                print(f"📧 Processing {i + 1}/{len(emails)}: {email} ({current_progress['progress_percentage']}%)")
                
                # Check if we need a fresh token (every 20 requests or if close to expiry)
                if i > 0 and i % 20 == 0:
                    print("🔄 Checking token freshness...")
                    fresh_token = await get_fresh_token()
                    if fresh_token != token:
                        print("🔑 Using refreshed token")
                        token = fresh_token
                        extractor = LinkedInProfileExtractor(token)
                
                # Make the API call
                profile_data = await extractor.fetch_linkedin_profile(email)
                
                result = {
                    "email": email,
                    "success": True,
                    "data": profile_data,
                    "timestamp": datetime.now().isoformat(),
                    "processed_index": i + 1
                }
                
                results.append(result)
                
                # Save individual file if requested
                if save_individual_files:
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"linkedin_profile_{email.replace('@', '_at_').replace('.', '_')}_{timestamp}.json"
                        filepath = os.path.join("temp", filename)
                        
                        os.makedirs("temp", exist_ok=True)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(result, f, indent=2, ensure_ascii=False)
                        
                        result["saved_to_file"] = filepath
                        print(f"💾 Saved individual file: {filename}")
                    except Exception as file_error:
                        print(f"⚠️  Could not save individual file: {file_error}")
                
                print(f"✅ Successfully processed: {email}")
                
                # Standard delay between requests (except for the last one)
                if i < len(emails) - 1:
                    print(f"⏳ Waiting {delay_seconds} seconds...")
                    await asyncio.sleep(delay_seconds)
                
                # Long break every N profiles
                if ((i + 1) % long_break_interval == 0) and (i + 1 < len(emails)):
                    print(f"🛌 Taking {long_break_duration} second break after {i + 1} profiles...")
                    await asyncio.sleep(long_break_duration)
                    
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Error processing {email}: {error_msg}")
                
                error_entry = {
                    "email": email,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat(),
                    "processed_index": i + 1,
                    "progress": current_progress
                }
                
                errors.append(error_entry)
                
                if stop_on_error:
                    print("🛑 Stopping batch process due to error (stop_on_error=True)")
                    break
                else:
                    print("⚠️  Continuing despite error (stop_on_error=False)")
                    # Still wait before next request
                    if i < len(emails) - 1:
                        await asyncio.sleep(delay_seconds)
        
        # Calculate final statistics
        end_time = datetime.now()
        total_duration = end_time - start_time
        
        summary = {
            "success": True,
            "total_emails": len(emails),
            "processed": len(results),
            "errors": len(errors),
            "success_rate": round((len(results) / len(emails)) * 100, 2) if emails else 0,
            "processing_duration_seconds": total_duration.total_seconds(),
            "processing_duration_human": str(total_duration).split('.')[0],
            "average_time_per_email": round(total_duration.total_seconds() / len(emails), 2) if emails else 0,
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "configuration": {
                "delay_seconds": delay_seconds,
                "stop_on_error": stop_on_error,
                "save_individual_files": save_individual_files,
                "long_break_interval": long_break_interval,
                "long_break_duration": long_break_duration
            },
            "results": results,
            "errors": errors
        }
        
        print(f"\n📊 Enhanced batch processing completed:")
        print(f"   • Total emails: {len(emails)}")
        print(f"   • Successfully processed: {len(results)}")
        print(f"   • Errors: {len(errors)}")
        print(f"   • Success rate: {summary['success_rate']}%")
        print(f"   • Total duration: {summary['processing_duration_human']}")
        print(f"   • Average per email: {summary['average_time_per_email']}s")
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhanced batch processing error: {str(e)}")

@app.post("/profile/download")
async def download_linkedin_profile(request: dict):
    """Download LinkedIn profile as JSON file"""
    try:
        # Extract email from request body
        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required in request body")
        
        # Get fresh token
        token = await get_fresh_token()
        
        # Create extractor and fetch profile
        extractor = LinkedInProfileExtractor(token)
        profile_data = await extractor.fetch_linkedin_profile(email)
        
        # Create temporary file
        filename = f"linkedin_profile_{email.replace('@', '_at_').replace('.', '_')}.json"
        
        # Create response data
        response_data = {
            "email": email,
            "data": profile_data,
            "timestamp": datetime.now().isoformat(),
            "extracted_by": "LinkedIn Profile Extractor API"
        }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(response_data, f, indent=2)
            temp_path = f.name
        
        return FileResponse(
            path=temp_path,
            filename=filename,
            media_type='application/json'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading profile: {str(e)}")

@app.post("/profiles/batch/download")
async def download_linkedin_profiles_batch(request: dict):
    """Download LinkedIn profiles for multiple emails as JSON file"""
    try:
        # Extract emails and delay from request body
        emails = request.get("emails", [])
        delay_seconds = request.get("delay_seconds", 2)
        
        if not emails:
            raise HTTPException(status_code=400, detail="emails array is required in request body")
        
        if len(emails) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 emails allowed per batch")
        
        # Get batch results by calling the internal logic directly
        # Get fresh token
        token = await get_fresh_token()
        
        extractor = LinkedInProfileExtractor(token)
        results = []
        errors = []
        
        for i, email in enumerate(emails):
            try:
                print(f"Processing {i + 1}/{len(emails)}: {email}")
                
                profile_data = await extractor.fetch_linkedin_profile(email)
                
                results.append({
                    "email": email,
                    "success": True,
                    "data": profile_data,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Add delay between requests (except for the last one)
                if i < len(emails) - 1:
                    await asyncio.sleep(delay_seconds)
                
                # Longer delay every 10 profiles
                if (i + 1) % 10 == 0 and i + 1 < len(emails):
                    print(f"Taking 10 second break after {i + 1} profiles...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                error_msg = str(e)
                print(f"Error processing {email}: {error_msg}")
                
                errors.append({
                    "email": email,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Stop on error
                print("Stopping batch process due to error")
                break
        
        batch_result = {
            "success": True,
            "total_emails": len(emails),
            "processed": len(results),
            "errors": len(errors),
            "results": results,
            "errors_details": errors,
            "completed_at": datetime.now().isoformat()
        }
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"linkedin_profiles_batch_{timestamp}.json"
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(batch_result, f, indent=2)
            temp_path = f.name
        
        return FileResponse(
            path=temp_path,
            filename=filename,
            media_type='application/json'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading batch profiles: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Start the persistent session on startup"""
    print("🚀 API Server starting up...")
    try:
        await ensure_session_started()
        print("✅ Persistent session initialized")
    except Exception as e:
        print(f"⚠️  Could not start persistent session on startup: {e}")
        print("   Session will be started on first request")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        from persistent_session import stop_persistent_session
        stop_persistent_session()
        print("✅ Persistent session stopped")
    except Exception as e:
        print(f"⚠️  Error stopping session: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
