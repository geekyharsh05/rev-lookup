#!/usr/bin/env python3
"""
Enhanced Batch API Integration
Additional endpoints for the large-scale batch processing system
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os

from dynamo_token_manager import get_dynamo_token_manager, add_token_from_file
from memory_job_queue import get_memory_job_queue, JobPriority
from heartbeat_polling_service import get_heartbeat_service, HeartbeatConfig
from dynamodb_manager import get_dynamodb_manager

def validate_and_clean_emails(emails: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate and clean email list, return (clean_emails, invalid_emails)
    """
    clean_emails = []
    invalid_emails = []
    
    for email in emails:
        if not email or not isinstance(email, str):
            invalid_emails.append(f"Empty or non-string: {repr(email)}")
            continue
            
        # Strip whitespace and check for problematic characters
        clean_email = email.strip()
        
        if not clean_email:
            invalid_emails.append("Empty email after stripping")
            continue
            
        # Check for newlines/carriage returns
        if '\n' in clean_email or '\r' in clean_email:
            invalid_emails.append(f"Contains newlines: {repr(clean_email)}")
            continue
            
        # Basic email format validation
        if '@' not in clean_email or clean_email.count('@') != 1:
            invalid_emails.append(f"Invalid email format: {clean_email}")
            continue
            
        # Check for control characters
        if any(ord(char) < 32 and char not in ['\t'] for char in clean_email):
            invalid_emails.append(f"Contains control characters: {repr(clean_email)}")
            continue
            
        clean_emails.append(clean_email)
    
    return clean_emails, invalid_emails

def add_enhanced_batch_endpoints(app: FastAPI):
    """Add enhanced batch processing endpoints to existing FastAPI app"""
    
    # Get service instances
    token_manager = get_dynamo_token_manager()
    job_queue = get_memory_job_queue()
    heartbeat_service = get_heartbeat_service()
    
    # Get DynamoDB manager for LinkedIn profiles
    try:
        linkedin_dynamodb = get_dynamodb_manager()
        
        # If manager is None, try to initialize it
        if linkedin_dynamodb is None:
            print("🔄 LinkedIn DynamoDB manager not found, attempting to initialize...")
            from dynamodb_manager import initialize_dynamodb_manager
            import os
            
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_REGION', 'ap-south-1')
            table_name = os.getenv('DYNAMODB_TABLE_NAME', 'linkedin_profiles')
            
            linkedin_dynamodb = initialize_dynamodb_manager(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region,
                table_name=table_name
            )
        
        if linkedin_dynamodb:
            linkedin_db_available = True
            print("✅ LinkedIn profiles DynamoDB manager initialized")
        else:
            linkedin_db_available = False
            print("❌ Failed to initialize LinkedIn DynamoDB manager")
            
    except Exception as e:
        print(f"⚠️  LinkedIn profiles DynamoDB initialization failed: {e}")
        linkedin_dynamodb = None
        linkedin_db_available = False
    
    # ===== TOKEN MANAGEMENT ENDPOINTS =====
    
    @app.post("/tokens/add")
    async def add_single_token(request: Dict[str, str]):
        """Add a single Bearer token to DynamoDB"""
        token = request.get("token", "").strip()
        token_id = request.get("token_id")
        
        if not token:
            raise HTTPException(status_code=400, detail="Token is required")
        
        if not token.startswith("Bearer "):
            token = "Bearer " + token
        
        success = token_manager.add_token(token, token_id)
        
        if success:
            return {
                "success": True,
                "message": "Token added successfully to DynamoDB",
                "token_preview": token[:50] + "..."
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail="Failed to add token (invalid format or already exists)"
            )
    
    @app.post("/tokens/add-multiple")
    async def add_multiple_tokens(request: Dict[str, List[str]]):
        """Add multiple Bearer tokens at once"""
        tokens = request.get("tokens", [])
        
        if not tokens:
            raise HTTPException(status_code=400, detail="tokens array is required")
        
        # Ensure all tokens have Bearer prefix
        formatted_tokens = []
        for token in tokens:
            token = token.strip()
            if not token.startswith("Bearer "):
                token = "Bearer " + token
            formatted_tokens.append(token)
        
        results = token_manager.add_multiple_tokens(formatted_tokens)
        
        successful = sum(1 for success in results.values() if success)
        failed = len(tokens) - successful
        
        return {
            "success": True,
            "message": f"Added {successful}/{len(tokens)} tokens successfully",
            "results": {
                "successful": successful,
                "failed": failed,
                "details": results
            }
        }
    
    @app.post("/tokens/add-from-file")
    async def add_token_from_txt_file():
        """Add token from token.txt file to DynamoDB (single token only)"""
        import os
        
        # Check if file exists first
        if not os.path.exists("token.txt"):
            raise HTTPException(
                status_code=400,
                detail="token.txt file not found in current directory"
            )
        
        # Read and validate token
        try:
            with open("token.txt", "r") as f:
                token_content = f.read().strip()
            
            if not token_content:
                raise HTTPException(
                    status_code=400,
                    detail="token.txt file is empty"
                )
            
            print(f"📄 Found token in token.txt: {token_content[:50]}...")
            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error reading token.txt: {str(e)}"
            )
        
        # Try to add token
        try:
            success = add_token_from_file("token.txt")
            
            if success:
                return {
                    "success": True,
                    "message": "Token from token.txt added to DynamoDB successfully",
                    "token_preview": token_content[:50] + "..."
                }
            else:
                # Get more specific error information
                token_manager = get_dynamo_token_manager()
                token_status = token_manager.get_status()
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to add token - validation failed or DynamoDB error. Current tokens: {token_status['total_tokens']}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Internal error adding token: {str(e)}"
            )
    
    @app.post("/tokens/add-multiple-from-file")
    async def add_multiple_tokens_from_txt_file():
        """Add multiple tokens from token.txt file to DynamoDB
        
        Supports multiple formats:
        - One token per line
        - Comma-separated tokens
        - Space-separated tokens (where Bearer is the separator)
        - Mixed formats
        """
        import os
        from dynamo_token_manager import add_multiple_tokens_from_file
        
        # Check if file exists first
        if not os.path.exists("token.txt"):
            raise HTTPException(
                status_code=400,
                detail="token.txt file not found in current directory"
            )
        
        # Process multiple tokens
        try:
            result = add_multiple_tokens_from_file("token.txt")
            
            if result["success"]:
                return {
                    "success": True,
                    "message": result["message"],
                    "tokens_added": result["tokens_added"],
                    "tokens_failed": result["tokens_failed"],
                    "total_tokens": result["total_tokens"],
                    "details": result["details"]
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.get("error", "Failed to add tokens from file")
                )
                
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Internal error processing tokens from file: {str(e)}"
            )
    
    @app.get("/tokens/status")
    async def get_all_tokens_status():
        """Get status of all tokens in DynamoDB"""
        return token_manager.get_status()
    
    @app.delete("/tokens/{token_id}")
    async def delete_token(token_id: str):
        """Delete a specific token"""
        success = token_manager.delete_token(token_id)
        
        if success:
            return {"success": True, "message": f"Token {token_id} deleted"}
        else:
            raise HTTPException(status_code=404, detail="Token not found or deletion failed")
    
    # ===== JOB MANAGEMENT ENDPOINTS =====
    
    @app.post("/jobs/create-batch")
    async def create_batch_job(request: Dict[str, Any]):
        """Create a new batch processing job"""
        raw_emails = request.get("emails", [])
        priority_str = request.get("priority", "NORMAL").upper()
        config = request.get("config", {})
        
        if not raw_emails:
            raise HTTPException(status_code=400, detail="emails array is required")
        
        # Validate and clean emails
        emails, invalid_emails = validate_and_clean_emails(raw_emails)
        
        if invalid_emails:
            print(f"⚠️  Found {len(invalid_emails)} invalid emails:")
            for invalid in invalid_emails[:5]:  # Show first 5
                print(f"   - {invalid}")
            if len(invalid_emails) > 5:
                print(f"   ... and {len(invalid_emails) - 5} more")
        
        if not emails:
            raise HTTPException(
                status_code=400, 
                detail=f"No valid emails after validation. Found {len(invalid_emails)} invalid emails."
            )
        
        if not isinstance(emails, list):
            raise HTTPException(status_code=400, detail="emails must be an array")
        
        # Validate priority
        try:
            priority = JobPriority[priority_str]
        except KeyError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid priority. Must be one of: {[p.name for p in JobPriority]}"
            )
        
        # Check token availability
        available_capacity = token_manager.get_available_capacity()
        if available_capacity == 0:
            raise HTTPException(
                status_code=503,
                detail="No token capacity available. Please add tokens or wait for daily reset."
            )
        
        if available_capacity < len(emails):
            return JSONResponse(
                status_code=202,
                content={
                    "warning": f"Only {available_capacity} tokens available for {len(emails)} emails",
                    "recommendation": "Consider splitting into smaller batches or adding more tokens"
                }
            )
        
        # Extract token rotation config if provided
        requests_per_token = config.get("requests_per_token", 15)
        if requests_per_token < 1 or requests_per_token > 50:
            raise HTTPException(
                status_code=400,
                detail="requests_per_token must be between 1 and 50"
            )
        
        # Add token rotation config to job config
        job_config = {
            **config,
            "requests_per_token": requests_per_token
        }
        
        print(f"🔄 Token rotation: {requests_per_token} requests per token before switching")
        
        # Create job
        job_id = job_queue.create_job(emails, priority, job_config)
        
        return {
            "success": True,
            "job_id": job_id,
            "total_emails": len(emails),
            "priority": priority.name,
            "estimated_capacity_used": len(emails),
            "available_capacity": available_capacity,
            "linkedin_profiles_auto_save": linkedin_db_available,
            "token_rotation": {
                "requests_per_token": requests_per_token,
                "estimated_token_switches": max(1, len(emails) // requests_per_token),
                "description": f"Each token will be used for {requests_per_token} requests before rotating to the next"
            },
            "message": "Batch job created and queued for processing. LinkedIn profiles will be automatically saved to DynamoDB." if linkedin_db_available else "Batch job created. LinkedIn profiles auto-save not available - use manual save endpoint after completion."
        }
    
    @app.get("/jobs/{job_id}")
    async def get_job_details(job_id: str):
        """Get detailed information about a specific job"""
        job_details = job_queue.get_job_details(job_id)
        
        if not job_details:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return job_details
    
    @app.get("/jobs/{job_id}/results")
    async def get_job_results(job_id: str, limit: Optional[int] = None):
        """Get results for a specific job with LinkedIn profile save status"""
        results = job_queue.get_job_results(job_id, limit)
        
        if not results:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Add LinkedIn profile save statistics
        successful_results = results.get("results", [])
        saved_to_linkedin = sum(1 for r in successful_results if r.get("saved_to_linkedin_profiles"))
        failed_to_save = sum(1 for r in successful_results if r.get("saved_to_linkedin_profiles") == False)
        
        results["linkedin_profiles_stats"] = {
            "total_profiles_fetched": len(successful_results),
            "saved_to_linkedin_profiles": saved_to_linkedin,
            "failed_to_save_linkedin": failed_to_save,
            "linkedin_db_available": linkedin_db_available
        }
        
        return results
    
    @app.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        """Cancel a pending job"""
        success = job_queue.cancel_job(job_id)
        
        if success:
            return {"success": True, "message": f"Job {job_id} cancelled"}
        else:
            raise HTTPException(
                status_code=400, 
                detail="Job not found or cannot be cancelled (may already be processing)"
            )
    
    @app.get("/jobs/queue/status")
    async def get_queue_status():
        """Get overall job queue status"""
        return job_queue.get_queue_status()
    
    @app.get("/jobs/active")
    async def get_active_jobs():
        """Get all currently processing jobs"""
        return job_queue.get_active_jobs()
    
    @app.get("/jobs/pending")
    async def get_pending_jobs():
        """Get all pending jobs"""
        return job_queue.get_pending_jobs()
    
    @app.get("/jobs/recent")
    async def get_recent_completed_jobs(limit: int = 20):
        """Get recently completed jobs"""
        return job_queue.get_recent_completed_jobs(limit)
    
    @app.post("/jobs/{job_id}/save-to-linkedin-profiles")
    async def save_job_results_to_linkedin_profiles(job_id: str):
        """Manually save batch job results to LinkedIn profiles DynamoDB table"""
        if not linkedin_db_available:
            raise HTTPException(
                status_code=503,
                detail="LinkedIn profiles DynamoDB table is not available. Check AWS credentials and configuration."
            )
        
        # Get job results
        results = job_queue.get_job_results(job_id)
        if not results:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if results["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job is not completed yet. Current status: {results['status']}"
            )
        
        successful_results = results.get("results", [])
        if not successful_results:
            return {
                "success": True,
                "message": "No successful results to save",
                "saved_count": 0,
                "failed_count": 0
            }
        
        # Save results to LinkedIn profiles table
        saved_count = 0
        failed_count = 0
        save_errors = []
        
        for result in successful_results:
            try:
                if linkedin_dynamodb.save_profile(result):
                    saved_count += 1
                    print(f"✅ Saved profile for {result['email']} to linkedin_profiles")
                else:
                    failed_count += 1
                    save_errors.append(f"Failed to save {result['email']}")
                    print(f"❌ Failed to save profile for {result['email']}")
                    
            except Exception as e:
                failed_count += 1
                error_msg = f"Error saving {result['email']}: {str(e)}"
                save_errors.append(error_msg)
                print(f"❌ {error_msg}")
        
        return {
            "success": True,
            "message": f"Batch save completed",
            "job_id": job_id,
            "total_results": len(successful_results),
            "saved_count": saved_count,
            "failed_count": failed_count,
            "save_errors": save_errors[:10] if save_errors else [],  # Limit error list
            "linkedin_profiles_table": linkedin_dynamodb.table_name if linkedin_dynamodb else None
        }
    
    # ===== HEARTBEAT SERVICE ENDPOINTS =====
    
    @app.post("/service/start")
    async def start_heartbeat_service():
        """Start the heartbeat polling service"""
        try:
            heartbeat_service.start()
            return {
                "success": True,
                "message": "Heartbeat polling service started",
                "status": heartbeat_service.get_service_status()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start service: {str(e)}")
    
    @app.post("/service/stop")
    async def stop_heartbeat_service():
        """Stop the heartbeat polling service"""
        try:
            heartbeat_service.stop()
            return {
                "success": True,
                "message": "Heartbeat polling service stopped"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop service: {str(e)}")
    
    @app.get("/service/status")
    async def get_service_status():
        """Get comprehensive service status"""
        return heartbeat_service.get_service_status()
    
    @app.post("/service/config")
    async def update_service_config(config: Dict[str, Any]):
        """Update heartbeat service configuration"""
        try:
            heartbeat_service.update_config(config)
            return {
                "success": True,
                "message": "Service configuration updated",
                "new_config": config
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # ===== SYSTEM HEALTH ENDPOINTS =====
    
    @app.get("/system/health")
    async def system_health_check():
        """Comprehensive system health check"""
        try:
            token_status = token_manager.get_status()
            queue_status = job_queue.get_queue_status()
            service_status = heartbeat_service.get_service_status()
            
            # Calculate health score
            health_score = 100
            issues = []
            
            # Check token health
            if token_status['available_tokens'] == 0:
                health_score -= 30
                issues.append("No available tokens")
            elif token_status['available_tokens'] < 5:
                health_score -= 10
                issues.append("Low token availability")
            
            # Check queue health
            pending_jobs = queue_status['status_breakdown']['pending']
            if pending_jobs > 100:
                health_score -= 20
                issues.append("High number of pending jobs")
            elif pending_jobs > 50:
                health_score -= 10
                issues.append("Moderate number of pending jobs")
            
            # Check service health
            if not service_status['service']['is_running']:
                health_score -= 40
                issues.append("Heartbeat service not running")
            
            health_status = "excellent"
            if health_score < 60:
                health_status = "poor"
            elif health_score < 80:
                health_status = "fair"
            elif health_score < 95:
                health_status = "good"
            
            return {
                "timestamp": datetime.now().isoformat(),
                "health_score": health_score,
                "health_status": health_status,
                "issues": issues,
                "components": {
                    "token_manager": {
                        "status": "healthy" if token_status['available_tokens'] > 0 else "unhealthy",
                        "available_tokens": token_status['available_tokens'],
                        "total_tokens": token_status['total_tokens'],
                        "available_capacity": token_status['available_capacity']
                    },
                    "job_queue": {
                        "status": "healthy",
                        "pending_jobs": pending_jobs,
                        "processing_jobs": queue_status['status_breakdown']['processing'],
                        "total_jobs": queue_status['total_jobs']
                    },
                    "heartbeat_service": {
                        "status": "healthy" if service_status['service']['is_running'] else "unhealthy",
                        "is_running": service_status['service']['is_running'],
                        "active_processors": service_status['active_processing']['active_jobs_count'],
                        "uptime_seconds": service_status['service']['uptime_seconds']
                    }
                },
                "detailed_status": {
                    "tokens": token_status,
                    "queue": queue_status,
                    "service": service_status
                }
            }
            
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "health_score": 0,
                "health_status": "critical",
                "error": str(e),
                "issues": ["System health check failed"]
            }
    
    @app.get("/system/metrics")
    async def get_system_metrics():
        """Get system performance metrics"""
        token_status = token_manager.get_status()
        queue_status = job_queue.get_queue_status()
        service_status = heartbeat_service.get_service_status()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "tokens": {
                "total": token_status['total_tokens'],
                "available": token_status['available_tokens'],
                "usage_percentage": token_status['usage_percentage'],
                "daily_capacity": token_status['max_daily_capacity'],
                "used_capacity": token_status['total_daily_usage']
            },
            "jobs": {
                "total_created": queue_status['statistics']['total_jobs_created'],
                "total_completed": queue_status['statistics']['total_jobs_completed'],
                "success_rate": queue_status['statistics']['success_rate'],
                "pending": queue_status['status_breakdown']['pending'],
                "processing": queue_status['status_breakdown']['processing']
            },
            "emails": {
                "total_processed": queue_status['statistics']['total_emails_processed'],
                "total_failed": queue_status['statistics']['total_emails_failed'],
                "success_rate": queue_status['statistics']['email_success_rate']
            },
            "service": {
                "uptime_seconds": service_status['service']['uptime_seconds'],
                "jobs_processed": service_status['service']['jobs_processed'],
                "emails_processed": service_status['service']['emails_processed'],
                "active_processors": service_status['active_processing']['active_jobs_count']
            }
        }
    
    # ===== UTILITY ENDPOINTS =====
    
    @app.post("/system/cleanup")
    async def manual_cleanup():
        """Manually trigger cleanup of old jobs"""
        cleaned_jobs = job_queue.clear_completed_jobs(24)  # Clean jobs older than 24 hours
        
        return {
            "success": True,
            "message": f"Cleanup completed",
            "jobs_cleaned": cleaned_jobs
        }
    
    @app.get("/system/info")
    async def get_system_info():
        """Get basic system information"""
        return {
            "system": "Enhanced Batch LinkedIn Profile Processor",
            "version": "1.0.0",
            "features": [
                "DynamoDB token storage with TTL",
                "In-memory job queue",
                "Heartbeat polling service",
                "Multi-token rotation",
                "Rate limiting (500 requests/day per token)",
                "Real-time progress tracking",
                "Automatic error handling",
                "Graceful job cancellation",
                "Auto-save LinkedIn profiles to DynamoDB",
                "Manual batch save to linkedin_profiles table"
            ],
            "linkedin_profiles_integration": {
                "auto_save_enabled": linkedin_db_available,
                "table_name": linkedin_dynamodb.table_name if linkedin_dynamodb else None,
                "manual_save_endpoint": "/jobs/{job_id}/save-to-linkedin-profiles"
            },
            "endpoints": {
                "tokens": [
                    "POST /tokens/add",
                    "POST /tokens/add-multiple", 
                    "POST /tokens/add-from-file",
                    "GET /tokens/status",
                    "DELETE /tokens/{token_id}"
                ],
                "jobs": [
                    "POST /jobs/create-batch",
                    "GET /jobs/{job_id}",
                    "GET /jobs/{job_id}/results",
                    "POST /jobs/{job_id}/cancel",
                    "POST /jobs/{job_id}/save-to-linkedin-profiles",
                    "GET /jobs/queue/status",
                    "GET /jobs/active",
                    "GET /jobs/pending",
                    "GET /jobs/recent"
                ],
                "service": [
                    "POST /service/start",
                    "POST /service/stop", 
                    "GET /service/status",
                    "POST /service/config"
                ],
                "system": [
                    "GET /system/health",
                    "GET /system/metrics",
                    "POST /system/cleanup",
                    "GET /system/info"
                ]
            }
        }

def initialize_batch_system():
    """Initialize the batch processing system components"""
    print("🚀 Initializing Enhanced Batch Processing System...")
    
    # Initialize managers (they're created as singletons)
    token_manager = get_dynamo_token_manager()
    job_queue = get_memory_job_queue()
    heartbeat_service = get_heartbeat_service()
    
    # Initialize LinkedIn profiles DynamoDB manager
    try:
        from dynamodb_manager import initialize_dynamodb_manager
        import os
        
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION', 'ap-south-1')
        table_name = os.getenv('DYNAMODB_TABLE_NAME', 'linkedin_profiles')
        
        linkedin_db = initialize_dynamodb_manager(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
            table_name=table_name
        )
        print("✅ LinkedIn profiles DynamoDB manager initialized")
        
    except Exception as e:
        print(f"⚠️  LinkedIn profiles DynamoDB initialization failed: {e}")
        print("   Auto-save to linkedin_profiles table will not be available")
    
    # Add token from file if it exists
    if os.path.exists("token.txt"):
        success = add_token_from_file("token.txt")
        if success:
            print("✅ Added token from token.txt to DynamoDB")
    
    print("✅ Enhanced Batch Processing System initialized")
    
    return {
        "token_manager": token_manager,
        "job_queue": job_queue, 
        "heartbeat_service": heartbeat_service
    }

if __name__ == "__main__":
    # Test the system
    print("🧪 Testing Enhanced Batch API...")
    
    components = initialize_batch_system()
    
    # Test token manager
    print("\n🔑 Token Manager Status:")
    status = components["token_manager"].get_status()
    print(f"Total tokens: {status['total_tokens']}")
    print(f"Available tokens: {status['available_tokens']}")
    
    # Test job queue
    print("\n📋 Job Queue Status:")
    queue_status = components["job_queue"].get_queue_status()
    print(f"Total jobs: {queue_status['total_jobs']}")
    
    print("\n✅ Enhanced Batch API test completed")
