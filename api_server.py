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
from dynamodb_manager import get_dynamodb_manager, initialize_dynamodb_manager
from profile_database_manager import get_profile_database_manager, initialize_profile_database_manager
from profile_data_mapper import LinkedInProfileMapper
from dynamo_token_manager import get_dynamo_token_manager
import tempfile
from dotenv import load_dotenv

load_dotenv()

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
dynamodb_initialized: bool = False
profile_database_initialized: bool = False

class LinkedInProfileExtractor:
    def __init__(self, auth_token: str):
        # Sanitize auth token to prevent header injection
        self.auth_token = self._sanitize_header_value(auth_token)
        
    def _sanitize_header_value(self, value: str) -> str:
        """Remove newlines and carriage returns that could cause header injection"""
        if not value:
            return value
        # Remove \r, \n, and other control characters that could break HTTP headers
        sanitized = value.replace('\r', '').replace('\n', '').replace('\r\n', '')
        # Also remove other potential problematic characters
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in ['\t'])
        return sanitized.strip()
        
    def encode_email(self, email: str) -> str:
        # Sanitize email before encoding to prevent injection
        clean_email = self._sanitize_header_value(email)
        return clean_email.replace('@', '%40')
    
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
                    error_text = await response.text()
                    
                    # Handle specific error cases
                    if response.status == 403:
                        # Check if it's a user restriction error
                        if "User is restricted" in error_text:
                            raise HTTPException(
                                status_code=403,
                                detail=f"LinkedIn profile access restricted for {email}. User account may have privacy settings or restrictions."
                            )
                    elif response.status == 424:
                        # Failed dependency - usually means upstream service issue
                        if "User is restricted" in error_text:
                            raise HTTPException(
                                status_code=424,
                                detail=f"LinkedIn profile access denied for {email}. User may be restricted or have privacy settings enabled."
                            )
                    
                    # Generic error handling
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"LinkedIn API error: {response.status} - {error_text}"
                    )
                
                return await response.json()

async def ensure_session_started():
    """Ensure the persistent session is started"""
    global session_started
    
    if not session_started:
        with startup_lock:
            if not session_started:  # Double-check locking
                print("Starting persistent Outlook session...")
                
                # Run session startup in thread executor
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, start_persistent_session)
                
                if success:
                    session_started = True
                    print("✅ Persistent session started successfully!")
                else:
                    raise HTTPException(status_code=503, detail="Failed to start persistent session")
    
    return True

async def ensure_dynamodb_initialized():
    """Ensure DynamoDB is initialized with credentials"""
    global dynamodb_initialized
    
    if not dynamodb_initialized:
        try:
            # Get credentials from environment variables
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            table_name = os.getenv('DYNAMODB_TABLE_NAME', 'linkedin_profiles')
            
            if not aws_access_key_id or not aws_secret_access_key:
                print("⚠️  AWS credentials not found in environment variables")
                print("   Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
                return False
            
            # Initialize DynamoDB manager
            initialize_dynamodb_manager(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region,
                table_name=table_name
            )
            
            dynamodb_initialized = True
            print("✅ DynamoDB initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize DynamoDB: {str(e)}")
            return False
    
    return True

async def ensure_profile_database_initialized():
    """Ensure Profile Database is initialized with credentials"""
    global profile_database_initialized
    
    if not profile_database_initialized:
        try:
            # Get credentials from environment variables
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            
            if not aws_access_key_id or not aws_secret_access_key:
                print("⚠️  AWS credentials not found for Profile Database")
                print("   Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
                return False
            
            # Initialize Profile Database manager
            initialize_profile_database_manager(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region,
                table_name="profile_database"
            )
            
            profile_database_initialized = True
            print("✅ Profile Database initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize Profile Database: {str(e)}")
            return False
    
    return True

async def get_fresh_token() -> str:
    """Get a fresh Bearer token - prioritize DynamoDB bearer_token table over token.txt"""
    try:
        print("📄 Getting token for API request...")
        
        # Step 1: Try to get token from DynamoDB bearer_token table first
        try:
            dynamo_token_manager = get_dynamo_token_manager()
            if dynamo_token_manager:
                print("🔍 Checking DynamoDB bearer_token table...")
                token_result = dynamo_token_manager.get_available_token()
                
                if token_result:
                    token, token_id = token_result
                    print(f"✅ Using token from DynamoDB bearer_token table (ID: {token_id}): {token[:50]}...")
                    return token
                else:
                    print("⚠️  No available tokens found in DynamoDB bearer_token table")
            else:
                print("⚠️  DynamoDB token manager not available")
        except Exception as e:
            print(f"⚠️  Failed to get token from DynamoDB: {e}")
        
        # Step 2: Fallback to token.txt if no DynamoDB tokens available
        token_file = os.path.join(os.getcwd(), "token.txt")
        
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    token = f.read().strip()
                
                if token:
                    print(f"🔄 Fallback: Using token from token.txt: {token[:50]}...")
                    return token
                else:
                    print("⚠️  token.txt exists but is empty")
            except Exception as e:
                print(f"⚠️  Error reading token.txt: {e}")
        else:
            print("ℹ️  token.txt file does not exist")
        
        # Step 3: No token in DynamoDB or file, try to extract from existing session
        session_manager = get_session_manager()
        if session_manager and session_manager.browser and session_manager.is_logged_in:
            print("🔄 No tokens available, trying to extract from existing browser session...")
            try:
                fresh_token = session_manager.extract_bearer_token()
                if fresh_token:
                    # Try to save to DynamoDB first, fallback to token.txt
                    try:
                        dynamo_token_manager = get_dynamo_token_manager()
                        if dynamo_token_manager:
                            success = dynamo_token_manager.add_token(fresh_token)
                            if success:
                                print(f"✅ Extracted token saved to DynamoDB bearer_token table: {fresh_token[:50]}...")
                            else:
                                print("⚠️  Failed to save extracted token to DynamoDB, saving to token.txt...")
                                with open(token_file, 'w') as f:
                                    f.write(fresh_token)
                                os.chmod(token_file, 0o600)
                        else:
                            # Save to token.txt as fallback
                            with open(token_file, 'w') as f:
                                f.write(fresh_token)
                            os.chmod(token_file, 0o600)
                            print(f"✅ Extracted token saved to token.txt: {fresh_token[:50]}...")
                    except Exception as save_error:
                        print(f"⚠️  Error saving extracted token: {save_error}")
                    
                    return fresh_token
            except Exception as e:
                print(f"⚠️  Failed to extract from existing session: {e}")
        
        # Step 4: No token available anywhere
        print("❌ No Bearer tokens found in DynamoDB bearer_token table, token.txt file, or active browser session")
        
        raise HTTPException(
            status_code=401, 
            detail="No Bearer token found. Please add tokens to DynamoDB bearer_token table, create token.txt file, or extract a fresh token."
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
        "version": "2.1.0",
        "token_system": {
            "primary_storage": "DynamoDB bearer_token table",
            "fallback_storage": "token.txt file",
            "priority_order": "DynamoDB > token.txt > browser extraction",
            "note": "System now prioritizes DynamoDB bearer_token table over token.txt"
        },
        "endpoints": {
            "POST /profile": "Get LinkedIn profile for single email (body: {email: 'user@example.com'})",
            "POST /profiles/batch": "Enhanced batch processing with automatic profile_database mapping (body: {emails: [...], delay_seconds: 2, stop_on_error: true, save_individual_files: false, save_to_dynamodb: true, long_break_interval: 10, long_break_duration: 10})",
            "POST /profile/mapped": "Get LinkedIn profile mapped to profile_database format (body: {email: 'user@example.com', save_to_profile_db: true})",
            "POST /profile/map-from-linkedin-profiles": "Map existing data from linkedin_profiles to profile_database (body: {email: 'user@example.com', save_to_profile_db: true})",
            "POST /profiles/batch-map-from-linkedin": "Batch map profiles from linkedin_profiles to profile_database (body: {emails: [...]})",
            "POST /profile/download": "Download single LinkedIn profile as JSON file (body: {email: 'user@example.com'})",
            "GET /health": "Health check",
            "GET /token/status": "Check token status from both DynamoDB and token.txt",
            "POST /token/refresh": "Force token refresh (may open browser)",
            "POST /token/manual": "Manually upload Bearer token to both DynamoDB and token.txt (body: {token: 'Bearer xyz...'})"
        },
        "database_tables": {
            "bearer_token": "Primary token storage with automatic expiry and usage tracking",
            "linkedin_profiles": "Original API responses (email + timestamp as keys)",
            "profile_database": "Formatted profiles with mapped structure (id as key)"
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
        "token_available": get_bearer_token() is not None,
        "dynamodb_initialized": dynamodb_initialized,
        "profile_database_initialized": profile_database_initialized
    }

@app.get("/token/status")
async def token_status():
    """Enhanced token status with DynamoDB and file-based token information"""
    # Get status from session manager
    session_manager = get_session_manager()
    token_manager = get_token_manager()
    
    session_status = {
        "session_started": session_started,
        "session_active": session_manager.is_logged_in if session_manager else False,
        "session_token_timestamp": session_manager.token_timestamp.isoformat() if session_manager and session_manager.token_timestamp else None,
    }
    
    # Get DynamoDB token status
    dynamodb_status = {}
    try:
        dynamo_token_manager = get_dynamo_token_manager()
        if dynamo_token_manager:
            dynamodb_status = dynamo_token_manager.get_status()
            dynamodb_status["source"] = "DynamoDB bearer_token table"
        else:
            dynamodb_status = {
                "source": "DynamoDB bearer_token table",
                "available": False,
                "error": "DynamoDB token manager not available"
            }
    except Exception as e:
        dynamodb_status = {
            "source": "DynamoDB bearer_token table", 
            "available": False,
            "error": str(e)
        }
    
    # Get file-based token status
    file_token_status = {}
    try:
        token_status_data = token_manager.get_token_status()
        file_token_status = {
            **token_status_data,
            "source": "token.txt file"
        }
    except Exception as e:
        file_token_status = {
            "source": "token.txt file",
            "available": False,
            "error": str(e)
        }
    
    return {
        **session_status,
        "dynamodb_tokens": dynamodb_status,
        "file_token": file_token_status,
        "token_priority": "DynamoDB bearer_token table > token.txt file > browser session extraction",
        "auto_refresh_active": token_manager.auto_refresh_thread.is_alive() if token_manager and token_manager.auto_refresh_thread else False
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
    """Manually upload a Bearer token - saves to both DynamoDB and token.txt"""
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
        
        # Save to DynamoDB first (primary storage)
        dynamodb_success = False
        try:
            dynamo_token_manager = get_dynamo_token_manager()
            if dynamo_token_manager:
                dynamodb_success = dynamo_token_manager.add_token(token)
                if dynamodb_success:
                    print("✅ Token saved to DynamoDB bearer_token table")
                else:
                    print("⚠️  Failed to save token to DynamoDB")
        except Exception as e:
            print(f"⚠️  Error saving to DynamoDB: {e}")
        
        # Save to token.txt (fallback storage)
        file_success = False
        try:
            token_manager = get_token_manager()
            if token_manager.save_token_to_file(token):
                token_manager.current_token = token
                token_manager.token_expires_at = token_manager.get_token_expiration(token)
                file_success = True
                print("✅ Token saved to token.txt file")
        except Exception as e:
            print(f"⚠️  Error saving to token.txt: {e}")
        
        # Return success if either storage method worked
        if dynamodb_success or file_success:
            storage_info = []
            if dynamodb_success:
                storage_info.append("DynamoDB bearer_token table")
            if file_success:
                storage_info.append("token.txt file")
            
            return {
                "success": True,
                "message": f"Token uploaded and saved successfully to: {', '.join(storage_info)}",
                "token_preview": token[:50] + "...",
                "saved_to": storage_info,
                "primary_storage": "DynamoDB bearer_token table" if dynamodb_success else "token.txt file"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save token to any storage location")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual token upload failed: {str(e)}")

@app.post("/profile")
async def get_linkedin_profile(request: dict):
    """Get LinkedIn profile for a single email"""
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
    """Enhanced batch processing with JavaScript-style logic and progress tracking"""
    try:
        # Extract configuration from request
        emails = request.get("emails", [])
        delay_seconds = request.get("delay_seconds", 2)
        stop_on_error = request.get("stop_on_error", True)
        save_individual_files = request.get("save_individual_files", False)
        save_to_dynamodb = request.get("save_to_dynamodb", True)  # DynamoDB option
        long_break_interval = request.get("long_break_interval", 10)  # Every N profiles
        long_break_duration = request.get("long_break_duration", 10)  # Seconds
        
        if not emails:
            raise HTTPException(status_code=400, detail="emails array is required in request body")
        
        print(f"🚀 Starting enhanced batch processing for {len(emails)} emails")
        print(f"⚙️  Config: delay={delay_seconds}s, stop_on_error={stop_on_error}, save_to_dynamodb={save_to_dynamodb}, long_break_every={long_break_interval}")
        
        # Initialize DynamoDB if requested
        dynamodb_manager = None
        profile_database_manager = None
        
        if save_to_dynamodb:
            try:
                # Initialize linkedin_profiles table
                await ensure_dynamodb_initialized()
                dynamodb_manager = get_dynamodb_manager()
                if not dynamodb_manager:
                    print("⚠️  DynamoDB not available, will skip saving to linkedin_profiles table")
                    save_to_dynamodb = False
                else:
                    print("✅ DynamoDB ready for saving to linkedin_profiles table")
                
                # Initialize profile_database table
                await ensure_profile_database_initialized()
                profile_database_manager = get_profile_database_manager()
                if not profile_database_manager:
                    print("⚠️  Profile Database not available, will skip saving to profile_database table")
                else:
                    print("✅ Profile Database ready for saving mapped profiles")
                
            except Exception as e:
                print(f"⚠️  Database initialization failed: {e}")
                print("   Will continue without saving to databases")
                save_to_dynamodb = False
        
        # Get fresh token with automatic refresh
        token = await get_fresh_token()
        extractor = LinkedInProfileExtractor(token)
        
        # Results tracking
        results = []
        errors = []
        start_time = datetime.now()
        dynamodb_stats = {
            "profiles_saved": 0,
            "profiles_replaced": 0,
            "profiles_failed": 0,
            "total_deleted": 0
        }
        profile_database_stats = {
            "profiles_saved": 0,
            "profiles_failed": 0
        }
        
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
                }
                
                results.append(result)
                
                # Save to DynamoDB if requested
                if save_to_dynamodb and dynamodb_manager:
                    try:
                        # Save to linkedin_profiles table (original format)
                        save_success = dynamodb_manager.save_profile(result)
                        if save_success:
                            result["saved_to_dynamodb"] = True
                            result["dynamodb_action"] = "saved_and_replaced"
                            dynamodb_stats["profiles_saved"] += 1
                            dynamodb_stats["profiles_replaced"] += 1
                            print(f"💾 Saved to linkedin_profiles table (replaced existing): {email}")
                        else:
                            result["saved_to_dynamodb"] = False
                            result["dynamodb_action"] = "failed"
                            dynamodb_stats["profiles_failed"] += 1
                            print(f"⚠️  Failed to save to linkedin_profiles table: {email}")
                            
                        # Map and save to profile_database table (formatted structure)
                        if profile_database_manager:
                            try:
                                mapped_profile = LinkedInProfileMapper.map_profile_data(result, email)
                                profile_save_success = profile_database_manager.save_profile(mapped_profile)
                                
                                if profile_save_success:
                                    result["saved_to_profile_database"] = True
                                    profile_database_stats["profiles_saved"] += 1
                                    print(f"🗃️  Saved mapped profile to profile_database table: {email}")
                                else:
                                    result["saved_to_profile_database"] = False
                                    profile_database_stats["profiles_failed"] += 1
                                    print(f"⚠️  Failed to save mapped profile to profile_database table: {email}")
                                    
                            except Exception as mapping_error:
                                result["saved_to_profile_database"] = False
                                result["profile_database_error"] = str(mapping_error)
                                profile_database_stats["profiles_failed"] += 1
                                print(f"❌ Profile mapping/saving error for {email}: {mapping_error}")
                        else:
                            result["saved_to_profile_database"] = False
                            result["profile_database_error"] = "Profile Database manager not available"
                            
                    except Exception as db_error:
                        result["saved_to_dynamodb"] = False
                        result["dynamodb_action"] = "error"
                        result["dynamodb_error"] = str(db_error)
                        result["saved_to_profile_database"] = False
                        result["profile_database_error"] = "DynamoDB error prevented profile database save"
                        dynamodb_stats["profiles_failed"] += 1
                        profile_database_stats["profiles_failed"] += 1
                        print(f"❌ DynamoDB save error for {email}: {db_error}")
                
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
                "save_to_dynamodb": save_to_dynamodb,
                "long_break_interval": long_break_interval,
                "long_break_duration": long_break_duration
            },
            "dynamodb_stats": dynamodb_stats if save_to_dynamodb else None,
            "profile_database_stats": profile_database_stats if save_to_dynamodb else None,
            "results": results,
            "errors": errors
        }
        
        print(f"\n📊 Enhanced batch processing completed:")
        print(f"   • Total emails: {len(emails)}")
        print(f"   • Successfully processed: {len(results)}")
        print(f"   • Errors: {len(errors)}")
        print(f"   • Success rate: {summary['success_rate']}%")
        if save_to_dynamodb and dynamodb_stats:
            print(f"   • linkedin_profiles: {dynamodb_stats['profiles_saved']} saved/replaced, {dynamodb_stats['profiles_failed']} failed")
        if save_to_dynamodb and profile_database_stats:
            print(f"   • profile_database: {profile_database_stats['profiles_saved']} saved, {profile_database_stats['profiles_failed']} failed")
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

@app.post("/profile/mapped")
async def get_mapped_linkedin_profile(request: dict):
    """Get LinkedIn profile mapped to profile_database structure and optionally save"""
    try:
        # Extract email from request body
        email = request.get("email")
        save_to_profile_db = request.get("save_to_profile_db", True)
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required in request body")
        
        # Get fresh token
        token = await get_fresh_token()
        
        # Create extractor and fetch profile
        extractor = LinkedInProfileExtractor(token)
        profile_data = await extractor.fetch_linkedin_profile(email)
        
        # Create result structure similar to what's saved in linkedin_profiles
        result = {
            "email": email,
            "success": True,
            "data": profile_data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Map the profile data to profile_database structure
        mapped_profile = LinkedInProfileMapper.map_profile_data(result, email)
        
        response = {
            "success": True,
            "email": email,
            "raw_data": profile_data,
            "mapped_data": mapped_profile,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save to profile_database if requested
        if save_to_profile_db:
            try:
                await ensure_profile_database_initialized()
                profile_database_manager = get_profile_database_manager()
                
                if profile_database_manager:
                    # Save the mapped profile to profile_database table
                    save_success = profile_database_manager.save_profile(mapped_profile)
                    
                    response["saved_to_profile_database"] = save_success
                    
                    if save_success:
                        print(f"✅ Mapped profile saved to profile_database table: {email}")
                    else:
                        print(f"⚠️  Failed to save mapped profile to profile_database table: {email}")
                else:
                    response["saved_to_profile_database"] = False
                    response["profile_database_error"] = "Profile Database manager not available"
                    
            except Exception as db_error:
                print(f"❌ Profile Database save error for {email}: {db_error}")
                response["saved_to_profile_database"] = False
                response["profile_database_error"] = str(db_error)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching mapped profile: {str(e)}")

@app.post("/profile/map-from-linkedin-profiles")
async def map_from_linkedin_profiles_table(request: dict):
    """Map data from linkedin_profiles table to profile_database format"""
    try:
        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        # Get data from linkedin_profiles table
        await ensure_dynamodb_initialized()
        dynamodb_manager = get_dynamodb_manager()
        if not dynamodb_manager:
            raise HTTPException(status_code=503, detail="LinkedIn profiles database not available")
        
        # Query the linkedin_profiles table
        profile_record = dynamodb_manager.get_profile(email)
        
        if not profile_record:
            raise HTTPException(status_code=404, detail=f"Profile not found for {email}")
        
        # Map the data using your existing structure
        mapped_profile = LinkedInProfileMapper.map_profile_data(profile_record, email)
        
        # Save to profile_database table
        save_to_profile_db = request.get("save_to_profile_db", True)
        saved = False
        
        if save_to_profile_db:
            try:
                await ensure_profile_database_initialized()
                profile_database_manager = get_profile_database_manager()
                if profile_database_manager:
                    saved = profile_database_manager.save_profile(mapped_profile)
                    if saved:
                        print(f"✅ Mapped and saved profile from linkedin_profiles to profile_database: {email}")
            except Exception as e:
                print(f"❌ Error saving mapped profile: {e}")
        
        return {
            "success": True,
            "email": email,
            "original_data": profile_record,
            "mapped_data": mapped_profile,
            "saved_to_profile_database": saved,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mapping error: {str(e)}")

@app.post("/profiles/batch-map-from-linkedin")
async def batch_map_from_linkedin_profiles(request: dict):
    """Batch map profiles from linkedin_profiles table to profile_database table"""
    try:
        emails = request.get("emails", [])
        if not emails:
            raise HTTPException(status_code=400, detail="emails array is required")
        
        await ensure_dynamodb_initialized()
        dynamodb_manager = get_dynamodb_manager()
        if not dynamodb_manager:
            raise HTTPException(status_code=503, detail="LinkedIn profiles database not available")
        
        await ensure_profile_database_initialized()
        profile_database_manager = get_profile_database_manager()
        if not profile_database_manager:
            raise HTTPException(status_code=503, detail="Profile database not available")
        
        results = []
        errors = []
        
        for email in emails:
            try:
                # Get from linkedin_profiles table
                profile_record = dynamodb_manager.get_profile(email)
                
                if profile_record:
                    # Map the data
                    mapped_profile = LinkedInProfileMapper.map_profile_data(profile_record, email)
                    
                    # Save to profile_database table
                    saved = profile_database_manager.save_profile(mapped_profile)
                    
                    results.append({
                        "email": email,
                        "success": True,
                        "mapped": True,
                        "saved_to_profile_database": saved
                    })
                    
                    print(f"✅ Mapped and saved profile for {email}")
                else:
                    errors.append({
                        "email": email,
                        "error": "Profile not found in linkedin_profiles table"
                    })
                    print(f"❌ Profile not found for {email}")
                    
            except Exception as e:
                errors.append({
                    "email": email,
                    "error": str(e)
                })
                print(f"❌ Error processing {email}: {e}")
        
        return {
            "success": True,
            "total_emails": len(emails),
            "mapped_successfully": len(results),
            "errors": len(errors),
            "results": results,
            "error_details": errors,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch mapping error: {str(e)}")


# Add enhanced batch processing endpoints
try:
    from enhanced_batch_api import add_enhanced_batch_endpoints, initialize_batch_system
    add_enhanced_batch_endpoints(app)
    print("✅ Enhanced batch processing endpoints added")
except ImportError as e:
    print(f"⚠️  Enhanced batch processing not available: {e}")

@app.on_event("startup")
async def startup_event():
    """Start the persistent session and batch processing system on startup"""
    print("🚀 API Server starting up...")
    
    # Start existing session
    try:
        await ensure_session_started()
        print("✅ Persistent session initialized")
    except Exception as e:
        print(f"Could not start persistent session on startup: {e}")
        print("   Session will be started on first request")
    
    # Initialize batch processing system
    try:
        from enhanced_batch_api import initialize_batch_system
        from heartbeat_polling_service import start_heartbeat_service
        
        # Initialize components
        initialize_batch_system()
        
        # Start heartbeat service
        start_heartbeat_service()
        
        print("✅ Enhanced batch processing system started")
    except Exception as e:
        print(f"⚠️  Could not start batch processing system: {e}")
        print("   Batch processing features may not be available")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 API Server shutting down...")
    
    # Stop batch processing system
    try:
        from heartbeat_polling_service import stop_heartbeat_service
        stop_heartbeat_service()
        print("✅ Batch processing system stopped")
    except Exception as e:
        print(f"⚠️  Error stopping batch processing system: {e}")
    
    # Stop persistent session
    try:
        from persistent_session import stop_persistent_session
        stop_persistent_session()
        print("✅ Persistent session stopped")
    except Exception as e:
        print(f"❌ Error stopping session: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
