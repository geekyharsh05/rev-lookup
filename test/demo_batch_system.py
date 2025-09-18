#!/usr/bin/env python3
"""
Demo Script for Enhanced Batch Processing System
Tests the complete workflow with your existing token
"""

import requests
import json
import time
from datetime import datetime
import os

# API base URL
BASE_URL = "http://localhost:8000"

def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"🔥 {title}")
    print(f"{'='*60}")

def print_status(message, status="info"):
    """Print status message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
    print(f"[{timestamp}] {emoji.get(status, 'ℹ️')} {message}")

def make_request(method, endpoint, data=None):
    """Make HTTP request with error handling"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.text
            
    except requests.exceptions.ConnectionError:
        return False, "Connection error - make sure the API server is running"
    except Exception as e:
        return False, str(e)

def test_system_health():
    """Test system health and connectivity"""
    print_section("SYSTEM HEALTH CHECK")
    
    success, result = make_request("GET", "/system/health")
    if success:
        health_score = result.get("health_score", 0)
        health_status = result.get("health_status", "unknown")
        
        print_status(f"Health Score: {health_score}/100 ({health_status})", 
                    "success" if health_score > 80 else "warning")
        
        components = result.get("components", {})
        for component, status in components.items():
            component_status = status.get("status", "unknown")
            print_status(f"{component}: {component_status}", 
                        "success" if component_status == "healthy" else "warning")
        
        if result.get("issues"):
            print_status(f"Issues: {', '.join(result['issues'])}", "warning")
        
        return True
    else:
        print_status(f"Health check failed: {result}", "error")
        return False

def add_token_from_file():
    """Add the token from token.txt to DynamoDB"""
    print_section("TOKEN MANAGEMENT")
    
    # Check if token.txt exists
    if not os.path.exists("token.txt"):
        print_status("token.txt not found", "error")
        return False
    
    # Read token from file
    with open("token.txt", "r") as f:
        token = f.read().strip()
    
    if not token:
        print_status("token.txt is empty", "error")
        return False
    
    print_status(f"Found token in token.txt: {token[:50]}...", "info")
    
    # Add token via API
    success, result = make_request("POST", "/tokens/add-from-file")
    if success:
        print_status("Token added to DynamoDB successfully", "success")
        return True
    else:
        print_status(f"Failed to add token: {result}", "error")
        return False

def show_token_status():
    """Display current token status"""
    success, result = make_request("GET", "/tokens/status")
    if success:
        print_status(f"Total tokens: {result['total_tokens']}", "info")
        print_status(f"Available tokens: {result['available_tokens']}", "info")
        print_status(f"Available capacity: {result['available_capacity']} requests", "info")
        print_status(f"Usage: {result['usage_percentage']:.1f}%", "info")
        
        # Show token details
        for token_detail in result.get('token_details', [])[:3]:  # Show first 3 tokens
            print_status(f"Token {token_detail['token_id']}: "
                        f"{token_detail['remaining_usage']}/500 remaining", "info")
        
        return result
    else:
        print_status(f"Failed to get token status: {result}", "error")
        return None

def create_demo_batch_job():
    """Create a demo batch job with sample emails"""
    print_section("BATCH JOB CREATION")
    
    # Sample emails for testing
    demo_emails = [
        "john.doe@microsoft.com",
        "jane.smith@google.com", 
        "bob.wilson@amazon.com",
        "alice.johnson@apple.com",
        "charlie.brown@meta.com"
    ]
    
    print_status(f"Creating batch job with {len(demo_emails)} emails", "info")
    
    job_data = {
        "emails": demo_emails,
        "priority": "HIGH",
        "config": {
            "delay_seconds": 2,
            "save_to_dynamodb": True
        }
    }
    
    success, result = make_request("POST", "/jobs/create-batch", job_data)
    if success:
        job_id = result["job_id"]
        print_status(f"Batch job created successfully: {job_id}", "success")
        print_status(f"Priority: {result['priority']}", "info")
        print_status(f"Total emails: {result['total_emails']}", "info")
        return job_id
    else:
        print_status(f"Failed to create batch job: {result}", "error")
        return None

def monitor_job_progress(job_id, max_wait_time=300):
    """Monitor job progress until completion"""
    print_section(f"MONITORING JOB: {job_id}")
    
    start_time = time.time()
    last_progress = -1
    
    while time.time() - start_time < max_wait_time:
        success, result = make_request("GET", f"/jobs/{job_id}")
        if not success:
            print_status(f"Failed to get job status: {result}", "error")
            break
        
        status = result["status"]
        progress = result["progress_percentage"]
        processed = result["processed_emails"]
        failed = result["failed_emails"]
        total = result["total_emails"]
        
        # Only print if progress changed
        if progress != last_progress:
            if result.get("current_email"):
                print_status(f"Processing: {result['current_email']} "
                           f"({processed + failed}/{total} - {progress:.1f}%)", "info")
            else:
                print_status(f"Status: {status} - {progress:.1f}% complete "
                           f"({processed} processed, {failed} failed)", "info")
            last_progress = progress
        
        # Check if job is complete
        if status in ["completed", "failed", "cancelled"]:
            print_status(f"Job {status}!", "success" if status == "completed" else "warning")
            
            if result.get("processing_time_seconds"):
                print_status(f"Processing time: {result['processing_time_seconds']:.1f} seconds", "info")
            
            # Show final results
            print_status(f"Final results: {processed} successful, {failed} failed", "info")
            return True
        
        time.sleep(3)  # Check every 3 seconds
    
    print_status("Monitoring timeout reached", "warning")
    return False

def show_job_results(job_id):
    """Display job results"""
    print_section(f"JOB RESULTS: {job_id}")
    
    success, result = make_request("GET", f"/jobs/{job_id}/results")
    if success:
        print_status(f"Total results: {result['total_results']}", "info")
        print_status(f"Total errors: {result['total_errors']}", "info")
        
        # Show sample results
        results = result.get("results", [])
        if results:
            print_status("Sample successful results:", "info")
            for i, res in enumerate(results[:3]):
                email = res["email"]
                timestamp = res["timestamp"]
                print_status(f"  {i+1}. {email} - {timestamp}", "success")
        
        # Show sample errors
        errors = result.get("errors", [])
        if errors:
            print_status("Sample errors:", "warning")
            for i, err in enumerate(errors[:3]):
                email = err["email"]
                error = err["error"]
                print_status(f"  {i+1}. {email} - {error}", "error")
        
        return True
    else:
        print_status(f"Failed to get job results: {result}", "error")
        return False

def show_system_metrics():
    """Display system performance metrics"""
    print_section("SYSTEM METRICS")
    
    success, result = make_request("GET", "/system/metrics")
    if success:
        tokens = result["tokens"]
        jobs = result["jobs"]
        emails = result["emails"]
        service = result["service"]
        
        print_status(f"Token Utilization: {tokens['usage_percentage']:.1f}% "
                    f"({tokens['used_capacity']}/{tokens['daily_capacity']})", "info")
        
        print_status(f"Job Success Rate: {jobs['success_rate']:.1f}% "
                    f"({jobs['total_completed']}/{jobs['total_created']})", "info")
        
        print_status(f"Email Success Rate: {emails['success_rate']:.1f}% "
                    f"({emails['total_processed']} processed)", "info")
        
        print_status(f"Service Uptime: {service['uptime_seconds']:.0f} seconds", "info")
        
        return True
    else:
        print_status(f"Failed to get system metrics: {result}", "error")
        return False

def main():
    """Main demo function"""
    print("🚀 Enhanced Batch Processing System Demo")
    print("=" * 60)
    print("This demo will test the complete batch processing workflow")
    print("Make sure the API server is running: python api_server.py")
    print()
    
    # Test system health
    if not test_system_health():
        print_status("System health check failed. Please check the API server.", "error")
        return
    
    # Add token from file
    if not add_token_from_file():
        print_status("Could not add token. Please check token.txt file.", "error")
        return
    
    # Show token status
    token_status = show_token_status()
    if not token_status or token_status["available_tokens"] == 0:
        print_status("No available tokens. Cannot proceed with demo.", "error")
        return
    
    # Create demo batch job
    job_id = create_demo_batch_job()
    if not job_id:
        print_status("Could not create batch job.", "error")
        return
    
    # Monitor job progress
    if monitor_job_progress(job_id):
        # Show job results
        show_job_results(job_id)
    
    # Show final system metrics
    show_system_metrics()
    
    print_section("DEMO COMPLETED")
    print_status("Demo completed successfully!", "success")
    print_status("You can now use the API endpoints to manage your batch processing", "info")
    print()
    print("🔗 Useful endpoints:")
    print("   • GET /system/health - System health check")
    print("   • GET /tokens/status - Token status")
    print("   • POST /jobs/create-batch - Create new batch job")
    print("   • GET /jobs/active - View active jobs")
    print("   • GET /system/metrics - Performance metrics")

if __name__ == "__main__":
    main()
