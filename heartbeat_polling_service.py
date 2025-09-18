#!/usr/bin/env python3
"""
Heartbeat Polling Service
Continuously polls for new jobs and processes them using available tokens
"""

import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import signal
import sys
import traceback

from dynamo_token_manager import get_dynamo_token_manager
from memory_job_queue import get_memory_job_queue, JobStatus, BatchJob
from dynamodb_manager import get_dynamodb_manager

@dataclass
class HeartbeatConfig:
    polling_interval: int = 3  # seconds
    max_concurrent_jobs: int = 5
    health_check_interval: int = 60  # seconds
    cleanup_interval: int = 1800  # 30 minutes
    max_job_age_hours: int = 48
    max_errors_per_token: int = 5
    delay_between_emails: float = 2.0  # seconds
    requests_per_token: int = 15  # Number of requests per token before rotation

class EmailProcessor:
    """Processes a single batch job using available tokens"""
    
    def __init__(self, job: BatchJob, config: HeartbeatConfig):
        self.job = job
        self.config = config
        self.is_running = False
        self.is_complete = False
        
        # Get managers
        self.token_manager = get_dynamo_token_manager()
        self.job_queue = get_memory_job_queue()
        
        # Fallback check - if DynamoDB token manager fails, provide alternative
        if not self.token_manager:
            print("⚠️  DynamoDB token manager not available, checking for token.txt fallback...")
            import os
            token_file = os.path.join(os.getcwd(), "token.txt")
            if os.path.exists(token_file):
                print("📄 Found token.txt, using as fallback token source")
                # We'll implement a fallback in the processing method
            else:
                raise ValueError("No token manager available and no token.txt file found")
        
        # Get DynamoDB manager for saving LinkedIn profiles
        try:
            self.dynamodb_manager = get_dynamodb_manager()
            
            # If manager is None, try to initialize it
            if self.dynamodb_manager is None:
                print("🔄 LinkedIn DynamoDB manager not initialized, attempting to initialize...")
                from dynamodb_manager import initialize_dynamodb_manager
                import os
                
                aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
                aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
                aws_region = os.getenv('AWS_REGION', 'us-east-1')
                table_name = os.getenv('DYNAMODB_TABLE_NAME', 'linkedin_profiles')
                
                self.dynamodb_manager = initialize_dynamodb_manager(
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    region_name=aws_region,
                    table_name=table_name
                )
            
            if self.dynamodb_manager:
                self.save_to_dynamodb = True
                print("✅ LinkedIn profiles will be saved to DynamoDB")
            else:
                self.save_to_dynamodb = False
                print("❌ Failed to initialize LinkedIn DynamoDB manager")
                
        except Exception as e:
            print(f"⚠️  DynamoDB manager initialization failed: {e}")
            self.dynamodb_manager = None
            self.save_to_dynamodb = False
        
        # Processing state
        self.current_email_index = 0
        self.results = []
        self.errors = []
        
        # Token rotation state
        self.current_token_id = None
        self.current_token = None
        self.requests_per_token = config.requests_per_token
        self.token_requests_made = 0
        
        # Threading
        self.process_thread = None
        self.stop_event = threading.Event()
        
    def start_async(self):
        """Start processing in background thread"""
        if self.is_running:
            return False
        
        # Set running state BEFORE starting thread to avoid race condition
        self.is_running = True
        self.process_thread = threading.Thread(target=self._process_emails, daemon=True)
        self.process_thread.start()
        return True
    
    def stop(self):
        """Stop processing"""
        self.is_running = False
        self.stop_event.set()
        
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=10)
    
    def _process_emails(self):
        """Main processing loop for batch job"""
        try:
            print(f"🚀 Starting processor for job {self.job.job_id} ({len(self.job.emails)} emails)")
            print(f"   Initial state: is_running={self.is_running}, stop_event={self.stop_event.is_set()}")
            
            for i, email in enumerate(self.job.emails):
                if self.stop_event.is_set() or not self.is_running:
                    print(f"🛑 Processing stopped for job {self.job.job_id}")
                    print(f"   Stop reason: stop_event={self.stop_event.is_set()}, is_running={self.is_running}")
                    break
                
                self.current_email_index = i
                success = self._process_single_email(email, i + 1)
                
                # Update job progress
                processed_count = len(self.results)
                failed_count = len(self.errors)
                
                self.job_queue.update_job_progress(
                    job_id=self.job.job_id,
                    processed=processed_count,
                    failed=failed_count,
                    current_email=email,
                    new_results=[self.results[-1]] if success and self.results else None,
                    new_errors=[self.errors[-1]] if not success and self.errors else None
                )
                
                # Delay between emails (except for the last one)
                if i < len(self.job.emails) - 1 and not self.stop_event.is_set():
                    time.sleep(self.config.delay_between_emails)
            
            # Mark job as completed
            if not self.stop_event.is_set():
                self.job_queue.complete_job(
                    job_id=self.job.job_id,
                    final_results=self.results,
                    final_errors=self.errors
                )
                
                # Provide detailed completion summary
                error_breakdown = {}
                for error in self.errors:
                    error_type = error.get("error_type", "unknown")
                    error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1
                
                print(f"✅ Completed job {self.job.job_id} ({len(self.results)} successful, {len(self.errors)} failed)")
                if error_breakdown:
                    print("   Error breakdown:")
                    for error_type, count in error_breakdown.items():
                        emoji = {"user_restricted": "🔒", "access_denied": "🚫", "data_validation": "🔍", 
                                "header_injection": "🛡️", "unknown": "❓"}.get(error_type, "❓")
                        print(f"   {emoji} {error_type}: {count}")
                else:
                    print("   No errors occurred!")
                
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            print(f"❌ Job {self.job.job_id} failed: {error_msg}")
            print(f"📋 Emails processed so far: {len(self.results)} successful, {len(self.errors)} failed")
            print(f"🔍 Current email index: {self.current_email_index}")
            print(f"📊 Job state: is_running={self.is_running}, stop_event={self.stop_event.is_set()}")
            print(f"Traceback: {traceback.format_exc()}")
            
            self.job_queue.fail_job(self.job.job_id, error_msg)
        
        finally:
            self.is_complete = True
            self.is_running = False
    
    def _process_single_email(self, email: str, email_num: int) -> bool:
        """Process a single email using LinkedIn API"""
        try:
            print(f"📧 Processing {email_num}/{len(self.job.emails)}: {email}")
            
            # Get available token using rotation
            print(f"🔍 Requesting token for {email} (attempt {email_num}/{len(self.job.emails)})")
            
            if self.token_manager:
                # Use DynamoDB token manager with rotation
                token_data = self.token_manager.get_rotating_token(
                    current_token_id=self.current_token_id,
                    requests_per_token=self.requests_per_token
                )
                
                if not token_data:
                    error_msg = "No available tokens from DynamoDB"
                    print(f"❌ Token request failed for {email}: {error_msg}")
                    # Check token status for debugging
                    status = self.token_manager.get_status()
                    print(f"   Token status: {status.get('available_tokens', 0)}/{status.get('total_tokens', 0)} available")
                    print(f"   Available capacity: {status.get('available_capacity', 0)} requests")
                    
                    self.errors.append({
                        "email": email,
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat(),
                        "email_number": email_num
                    })
                    return False
                
                token_id, token = token_data
                
                # Track token rotation state
                if token_id != self.current_token_id:
                    # Token switched
                    print(f"🔄 Switched from {self.current_token_id or 'None'} to {token_id}")
                    self.current_token_id = token_id
                    self.current_token = token
                    self.token_requests_made = 1
                else:
                    # Same token continued
                    self.token_requests_made += 1
            else:
                # Fallback to token.txt
                print("🔄 Using fallback token from token.txt")
                import os
                token_file = os.path.join(os.getcwd(), "token.txt")
                try:
                    with open(token_file, 'r') as f:
                        token = f.read().strip()
                    if not token:
                        error_msg = "token.txt is empty"
                        print(f"❌ {error_msg}")
                        self.errors.append({
                            "email": email,
                            "error": error_msg,
                            "timestamp": datetime.now().isoformat(),
                            "email_number": email_num
                        })
                        return False
                    
                    token_id = "token_txt_fallback"
                    print(f"✅ Using token from token.txt: {token[:50]}...")
                except Exception as e:
                    error_msg = f"Failed to read token.txt: {str(e)}"
                    print(f"❌ {error_msg}")
                    self.errors.append({
                        "email": email,
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat(),
                        "email_number": email_num
                    })
                    return False
            
            # Process the email
            try:
                # Additional validation before processing
                if not email or not email.strip():
                    raise ValueError("Email is empty or invalid")
                
                # Clean email of any potential problematic characters
                clean_email = email.strip()
                if '\n' in clean_email or '\r' in clean_email:
                    raise ValueError(f"Email contains invalid characters: {repr(clean_email)}")
                
                profile_data = self._fetch_linkedin_profile(clean_email, token)
                
                # Success
                result = {
                    "email": email,
                    "success": True,
                    "data": profile_data,
                    "timestamp": datetime.now().isoformat(),
                    "token_used": token_id,
                    "email_number": email_num
                }
                
                self.results.append(result)
                
                # Mark token as successful (if using DynamoDB manager)
                if self.token_manager and token_id != "token_txt_fallback":
                    self.token_manager.mark_token_success(token_id)
                
                # Save to LinkedIn profiles DynamoDB table
                if self.save_to_dynamodb and self.dynamodb_manager:
                    try:
                        save_success = self.dynamodb_manager.save_profile(result)
                        if save_success:
                            result["saved_to_linkedin_profiles"] = True
                            print(f"✅ {email}: Profile saved to linkedin_profiles table")
                        else:
                            result["saved_to_linkedin_profiles"] = False
                            print(f"⚠️  {email}: Failed to save to linkedin_profiles table")
                    except Exception as db_error:
                        result["saved_to_linkedin_profiles"] = False
                        result["dynamodb_error"] = str(db_error)
                        print(f"❌ {email}: DynamoDB save error - {db_error}")
                
                print(f"✅ {email}: Profile fetched successfully")
                return True
                
            except Exception as e:
                # Profile fetch failed
                error_msg = str(e)
                
                # Categorize errors for better handling
                error_type = "unknown"
                should_mark_token_error = True
                
                if "403" in error_msg or "User is restricted" in error_msg:
                    error_type = "user_restricted"
                    should_mark_token_error = False  # Not a token issue
                    print(f"🔒 {email}: User restricted or privacy settings enabled")
                elif "424" in error_msg and "Request denied" in error_msg:
                    error_type = "access_denied"
                    should_mark_token_error = False  # Not a token issue
                    print(f"🚫 {email}: Access denied by LinkedIn")
                elif "invalid characters" in error_msg.lower():
                    error_type = "data_validation"
                    should_mark_token_error = False  # Data issue, not token
                    print(f"🔍 {email}: Data validation error")
                elif "header injection" in error_msg.lower() or "newline" in error_msg.lower():
                    error_type = "header_injection"
                    should_mark_token_error = False  # Security issue, not token
                    print(f"🛡️  {email}: Header security validation failed")
                else:
                    print(f"❌ {email}: {error_msg}")
                
                self.errors.append({
                    "email": email,
                    "error": error_msg,
                    "error_type": error_type,
                    "timestamp": datetime.now().isoformat(),
                    "token_used": token_id,
                    "email_number": email_num
                })
                
                # Only mark token as having an error if it's actually a token-related issue
                if should_mark_token_error and self.token_manager and token_id != "token_txt_fallback":
                    self.token_manager.mark_token_error(token_id, error_msg)
                
                return False
        
        except Exception as e:
            # Unexpected error
            error_msg = f"Unexpected error: {str(e)}"
            self.errors.append({
                "email": email,
                "error": error_msg,
                "timestamp": datetime.now().isoformat(),
                "email_number": email_num
            })
            print(f"❌ {email}: {error_msg}")
            return False
    
    def _fetch_linkedin_profile(self, email: str, token: str) -> Dict:
        """Fetch LinkedIn profile using the existing API logic"""
        # Import here to avoid circular imports
        from api_server import LinkedInProfileExtractor
        
        # Create extractor
        extractor = LinkedInProfileExtractor(token)
        
        # Use asyncio to run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            profile_data = loop.run_until_complete(
                extractor.fetch_linkedin_profile(email)
            )
            return profile_data
        finally:
            loop.close()
    
    def get_stats(self) -> Dict:
        """Get current processing statistics"""
        total_processed = len(self.results) + len(self.errors)
        progress = (total_processed / len(self.job.emails)) * 100 if self.job.emails else 0
        
        return {
            "job_id": self.job.job_id,
            "total_emails": len(self.job.emails),
            "processed_emails": len(self.results),
            "failed_emails": len(self.errors),
            "current_email_index": self.current_email_index,
            "progress_percentage": round(progress, 2),
            "is_running": self.is_running,
            "is_complete": self.is_complete,
            "current_token_id": self.current_token_id[:8] + "..." if self.current_token_id else None,
            "token_requests_made": self.token_requests_made,
            "requests_per_token": self.requests_per_token
        }

class HeartbeatPollingService:
    """Main heartbeat service that orchestrates batch processing"""
    
    def __init__(self, config: HeartbeatConfig = None):
        self.config = config or HeartbeatConfig()
        self.is_running = False
        self.active_processors: Dict[str, EmailProcessor] = {}
        
        # Get managers
        self.job_queue = get_memory_job_queue()
        self.token_manager = get_dynamo_token_manager()
        
        # Threading
        self.heartbeat_thread = None
        self.health_thread = None
        self.cleanup_thread = None
        self.shutdown_event = threading.Event()
        
        # Metrics
        self.start_time = None
        self.jobs_processed = 0
        self.emails_processed = 0
        self.last_health_check = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("🫀 Heartbeat Polling Service initialized")
    
    def start(self):
        """Start the heartbeat polling service"""
        if self.is_running:
            print("⚠️  Heartbeat service already running")
            return
        
        print("🚀 Starting Heartbeat Polling Service...")
        print(f"   - Polling interval: {self.config.polling_interval}s")
        print(f"   - Max concurrent jobs: {self.config.max_concurrent_jobs}")
        print(f"   - Delay between emails: {self.config.delay_between_emails}s")
        
        self.is_running = True
        self.start_time = datetime.now()
        
        # Start main threads
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        self.health_thread = threading.Thread(target=self._health_loop, daemon=True)
        self.health_thread.start()
        
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        print("✅ Heartbeat Polling Service started")
    
    def stop(self, timeout: int = 30):
        """Stop the heartbeat service gracefully"""
        if not self.is_running:
            print("⚠️  Heartbeat service not running")
            return
        
        print("🛑 Stopping Heartbeat Polling Service...")
        self.is_running = False
        self.shutdown_event.set()
        
        # Stop all active processors
        for job_id, processor in list(self.active_processors.items()):
            print(f"   Stopping processor for job {job_id}...")
            processor.stop()
        
        # Wait for threads to finish
        for thread in [self.heartbeat_thread, self.health_thread, self.cleanup_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=timeout)
        
        print("✅ Heartbeat Polling Service stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🔔 Received signal {signum}, initiating graceful shutdown...")
        self.stop()
        sys.exit(0)
    
    def _heartbeat_loop(self):
        """Main heartbeat loop - continuously polls for jobs"""
        print("🫀 Heartbeat loop started")
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # Clean up completed processors
                self._cleanup_completed_processors()
                
                # Check if we can start new jobs
                if len(self.active_processors) < self.config.max_concurrent_jobs:
                    # Check token availability
                    available_capacity = self.token_manager.get_available_capacity()
                    
                    if available_capacity > 0:
                        # Get next job from queue
                        next_job = self.job_queue.get_next_job()
                        
                        if next_job:
                            self._start_job_processing(next_job)
                    else:
                        if len(self.active_processors) == 0:
                            print("⚠️  No token capacity available, waiting...")
                
                # Log current status periodically
                if len(self.active_processors) > 0:
                    active_jobs_info = []
                    for processor in self.active_processors.values():
                        stats = processor.get_stats()
                        active_jobs_info.append(f"{stats['job_id'][:8]}({stats['progress_percentage']:.1f}%)")
                    
                    print(f"🔄 Active jobs: {', '.join(active_jobs_info)}")
                
                # Sleep before next iteration
                time.sleep(self.config.polling_interval)
                
            except Exception as e:
                print(f"❌ Heartbeat loop error: {e}")
                print(f"Traceback: {traceback.format_exc()}")
                time.sleep(self.config.polling_interval * 2)
    
    def _start_job_processing(self, job: BatchJob):
        """Start processing a job"""
        try:
            # Create job-specific config with token rotation settings
            job_config = HeartbeatConfig()
            
            # Override with job-specific settings if provided
            if hasattr(job, 'config') and job.config:
                if 'requests_per_token' in job.config:
                    job_config.requests_per_token = job.config['requests_per_token']
                if 'delay_seconds' in job.config:
                    job_config.delay_between_emails = job.config['delay_seconds']
            
            processor = EmailProcessor(job, job_config)
            
            if processor.start_async():
                self.active_processors[job.job_id] = processor
                print(f"✅ Started processing job {job.job_id} ({len(job.emails)} emails)")
            else:
                print(f"❌ Failed to start processor for job {job.job_id}")
                self.job_queue.fail_job(job.job_id, "Failed to start processor")
                
        except Exception as e:
            error_msg = f"Failed to start job {job.job_id}: {str(e)}"
            print(f"❌ {error_msg}")
            self.job_queue.fail_job(job.job_id, error_msg)
    
    def _cleanup_completed_processors(self):
        """Remove completed processors"""
        completed_jobs = []
        
        for job_id, processor in list(self.active_processors.items()):
            if processor.is_complete:
                completed_jobs.append(job_id)
                self.jobs_processed += 1
                
                # Get final stats
                stats = processor.get_stats()
                self.emails_processed += stats['processed_emails']
                
                print(f"✅ Job {job_id} processor completed")
        
        # Remove completed processors
        for job_id in completed_jobs:
            if job_id in self.active_processors:
                del self.active_processors[job_id]
    
    def _health_loop(self):
        """Health monitoring loop"""
        print("🏥 Health monitoring started")
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                self._perform_health_check()
                time.sleep(self.config.health_check_interval)
                
            except Exception as e:
                print(f"❌ Health loop error: {e}")
                time.sleep(self.config.health_check_interval)
    
    def _perform_health_check(self):
        """Perform comprehensive health check"""
        self.last_health_check = datetime.now()
        
        # Get system status
        token_status = self.token_manager.get_status()
        queue_status = self.job_queue.get_queue_status()
        
        # Calculate uptime
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        print(f"🏥 Health Check ({self.last_health_check.strftime('%H:%M:%S')}):")
        print(f"   Uptime: {uptime:.0f}s")
        print(f"   Active processors: {len(self.active_processors)}/{self.config.max_concurrent_jobs}")
        print(f"   Available tokens: {token_status['available_tokens']}/{token_status['total_tokens']}")
        print(f"   Token capacity: {self.token_manager.get_available_capacity()} requests")
        print(f"   Pending jobs: {queue_status['status_breakdown']['pending']}")
        print(f"   Processing jobs: {queue_status['status_breakdown']['processing']}")
        print(f"   Jobs processed: {self.jobs_processed}")
        print(f"   Emails processed: {self.emails_processed}")
        
        # Check for issues
        if token_status['available_tokens'] == 0:
            print("⚠️  WARNING: No available tokens!")
        
        if queue_status['status_breakdown']['pending'] > 50:
            print("⚠️  WARNING: Large number of pending jobs!")
    
    def _cleanup_loop(self):
        """Periodic cleanup loop"""
        print("🧹 Cleanup monitoring started")
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # Cleanup old completed jobs
                cleaned = self.job_queue.clear_completed_jobs(self.config.max_job_age_hours)
                if cleaned > 0:
                    print(f"🧹 Cleaned up {cleaned} old jobs")
                
                time.sleep(self.config.cleanup_interval)
                
            except Exception as e:
                print(f"❌ Cleanup loop error: {e}")
                time.sleep(self.config.cleanup_interval)
    
    def get_service_status(self) -> Dict:
        """Get comprehensive service status"""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        # Get active job details
        active_job_details = []
        for processor in self.active_processors.values():
            stats = processor.get_stats()
            active_job_details.append(stats)
        
        return {
            "service": {
                "is_running": self.is_running,
                "uptime_seconds": uptime,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
                "jobs_processed": self.jobs_processed,
                "emails_processed": self.emails_processed
            },
            "active_processing": {
                "active_jobs_count": len(self.active_processors),
                "max_concurrent_jobs": self.config.max_concurrent_jobs,
                "active_jobs": active_job_details
            },
            "configuration": {
                "polling_interval": self.config.polling_interval,
                "max_concurrent_jobs": self.config.max_concurrent_jobs,
                "health_check_interval": self.config.health_check_interval,
                "delay_between_emails": self.config.delay_between_emails,
                "max_errors_per_token": self.config.max_errors_per_token
            },
            "token_manager": self.token_manager.get_status(),
            "job_queue": self.job_queue.get_queue_status()
        }
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update service configuration"""
        if 'polling_interval' in new_config:
            self.config.polling_interval = new_config['polling_interval']
        if 'max_concurrent_jobs' in new_config:
            self.config.max_concurrent_jobs = new_config['max_concurrent_jobs']
        if 'delay_between_emails' in new_config:
            self.config.delay_between_emails = new_config['delay_between_emails']
        if 'max_errors_per_token' in new_config:
            self.config.max_errors_per_token = new_config['max_errors_per_token']
        
        print(f"✅ Configuration updated: {new_config}")

# Global instance
_heartbeat_service = None

def get_heartbeat_service() -> HeartbeatPollingService:
    """Get or create global heartbeat service"""
    global _heartbeat_service
    if _heartbeat_service is None:
        _heartbeat_service = HeartbeatPollingService()
    return _heartbeat_service

def start_heartbeat_service(config: HeartbeatConfig = None) -> HeartbeatPollingService:
    """Start the global heartbeat service"""
    service = get_heartbeat_service()
    if config:
        service.config = config
    service.start()
    return service

def stop_heartbeat_service():
    """Stop the global heartbeat service"""
    global _heartbeat_service
    if _heartbeat_service:
        _heartbeat_service.stop()

if __name__ == "__main__":
    print("🚀 Heartbeat Polling Service Test")
    print("=" * 50)
    
    # Create test configuration
    config = HeartbeatConfig(
        polling_interval=5,
        max_concurrent_jobs=2,
        delay_between_emails=1.0
    )
    
    # Start service
    service = start_heartbeat_service(config)
    
    try:
        print("Press Ctrl+C to stop...")
        while True:
            time.sleep(60)
            status = service.get_service_status()
            print(f"Service status: Active jobs: {status['active_processing']['active_jobs_count']}")
    except KeyboardInterrupt:
        print("\n👋 Stopping service...")
        stop_heartbeat_service()
