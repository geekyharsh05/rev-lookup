#!/usr/bin/env python3
"""
In-Memory Job Queue System
Fast job queuing and processing with memory-based storage
"""

import uuid
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import heapq

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class BatchJob:
    job_id: str
    emails: List[str]
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processed_emails: int = 0
    failed_emails: int = 0
    results: List[Dict] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    current_email: Optional[str] = None
    
    @property
    def total_emails(self) -> int:
        return len(self.emails)
    
    @property
    def progress_percentage(self) -> float:
        if self.total_emails == 0:
            return 100.0
        return ((self.processed_emails + self.failed_emails) / self.total_emails) * 100
    
    @property
    def processing_time(self) -> Optional[float]:
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    @property
    def estimated_time_remaining(self) -> Optional[float]:
        if not self.started_at or self.processed_emails == 0:
            return None
        
        elapsed = (datetime.now() - self.started_at).total_seconds()
        avg_time_per_email = elapsed / max(1, self.processed_emails + self.failed_emails)
        remaining_emails = self.total_emails - (self.processed_emails + self.failed_emails)
        
        return remaining_emails * avg_time_per_email

class MemoryJobQueue:
    def __init__(self):
        self.jobs: Dict[str, BatchJob] = {}
        self.pending_queue = []  # Priority queue: (priority, timestamp, job_id)
        self.processing_jobs: Dict[str, BatchJob] = {}
        self.completed_jobs: Dict[str, BatchJob] = {}
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics
        self.total_jobs_created = 0
        self.total_jobs_completed = 0
        self.total_emails_processed = 0
        self.total_emails_failed = 0
        
        # Configuration
        self.max_completed_jobs = 1000  # Keep last 1000 completed jobs
        
        print("✅ Memory Job Queue initialized")
    
    def create_job(self, 
                   emails: List[str], 
                   priority: JobPriority = JobPriority.NORMAL,
                   config: Dict[str, Any] = None) -> str:
        """Create a new batch job"""
        with self.lock:
            job_id = str(uuid.uuid4())
            
            job = BatchJob(
                job_id=job_id,
                emails=emails.copy(),  # Make a copy to avoid external modifications
                priority=priority,
                config=config or {}
            )
            
            # Store job
            self.jobs[job_id] = job
            
            # Add to priority queue (negative priority for max-heap behavior)
            heapq.heappush(self.pending_queue, (-priority.value, time.time(), job_id))
            
            self.total_jobs_created += 1
            
            print(f"✅ Created job {job_id} with {len(emails)} emails (priority: {priority.name})")
            return job_id
    
    def get_next_job(self) -> Optional[BatchJob]:
        """Get the next highest priority job for processing"""
        with self.lock:
            while self.pending_queue:
                try:
                    _, timestamp, job_id = heapq.heappop(self.pending_queue)
                    
                    if job_id in self.jobs and self.jobs[job_id].status == JobStatus.PENDING:
                        job = self.jobs[job_id]
                        job.status = JobStatus.PROCESSING
                        job.started_at = datetime.now()
                        
                        # Move to processing jobs
                        self.processing_jobs[job_id] = job
                        
                        print(f"📋 Retrieved job {job_id} for processing ({job.total_emails} emails)")
                        return job
                        
                except IndexError:
                    break
            
            return None
    
    def update_job_progress(self, 
                           job_id: str, 
                           processed: int, 
                           failed: int,
                           current_email: str = None,
                           new_results: List[Dict] = None, 
                           new_errors: List[Dict] = None) -> bool:
        """Update job progress with new results"""
        with self.lock:
            if job_id not in self.jobs:
                return False
            
            job = self.jobs[job_id]
            job.processed_emails = processed
            job.failed_emails = failed
            job.current_email = current_email
            
            # Add new results
            if new_results:
                job.results.extend(new_results)
            if new_errors:
                job.errors.extend(new_errors)
            
            return True
    
    def complete_job(self, 
                     job_id: str, 
                     final_results: List[Dict] = None,
                     final_errors: List[Dict] = None) -> bool:
        """Mark job as completed"""
        with self.lock:
            if job_id not in self.jobs:
                return False
            
            job = self.jobs[job_id]
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.current_email = None
            
            if final_results is not None:
                job.results = final_results
            if final_errors is not None:
                job.errors = final_errors
            
            # Move to completed jobs
            self.completed_jobs[job_id] = job
            if job_id in self.processing_jobs:
                del self.processing_jobs[job_id]
            
            # Update statistics
            self.total_jobs_completed += 1
            self.total_emails_processed += job.processed_emails
            self.total_emails_failed += job.failed_emails
            
            # Cleanup old completed jobs if needed
            self._cleanup_old_completed_jobs()
            
            duration = job.processing_time or 0
            print(f"✅ Job {job_id} completed in {duration:.1f}s "
                  f"({job.processed_emails} processed, {job.failed_emails} failed)")
            return True
    
    def fail_job(self, job_id: str, error_message: str) -> bool:
        """Mark job as failed"""
        with self.lock:
            if job_id not in self.jobs:
                return False
            
            job = self.jobs[job_id]
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.current_email = None
            
            job.errors.append({
                "timestamp": datetime.now().isoformat(),
                "error": error_message,
                "type": "job_failure"
            })
            
            # Move to completed jobs
            self.completed_jobs[job_id] = job
            if job_id in self.processing_jobs:
                del self.processing_jobs[job_id]
            
            print(f"❌ Job {job_id} failed: {error_message}")
            return True
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job"""
        with self.lock:
            if job_id not in self.jobs:
                return False
            
            job = self.jobs[job_id]
            
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                
                # Move to completed jobs
                self.completed_jobs[job_id] = job
                
                print(f"🚫 Job {job_id} cancelled")
                return True
            
            return False
    
    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get job by ID"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """Get detailed job information"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            
            return {
                "job_id": job.job_id,
                "status": job.status.value,
                "priority": job.priority.name,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "total_emails": job.total_emails,
                "processed_emails": job.processed_emails,
                "failed_emails": job.failed_emails,
                "current_email": job.current_email,
                "progress_percentage": round(job.progress_percentage, 2),
                "processing_time_seconds": job.processing_time,
                "estimated_time_remaining_seconds": job.estimated_time_remaining,
                "results_count": len(job.results),
                "errors_count": len(job.errors),
                "config": job.config,
                "recent_results": job.results[-5:] if job.results else [],  # Last 5 results
                "recent_errors": job.errors[-5:] if job.errors else []  # Last 5 errors
            }
    
    def get_queue_status(self) -> Dict:
        """Get overall queue status"""
        with self.lock:
            status_counts = {status.value: 0 for status in JobStatus}
            priority_counts = {priority.name: 0 for priority in JobPriority}
            
            for job in self.jobs.values():
                status_counts[job.status.value] += 1
                priority_counts[job.priority.name] += 1
            
            # Calculate average processing time
            completed_jobs_with_time = [job for job in self.completed_jobs.values() 
                                      if job.processing_time and job.status == JobStatus.COMPLETED]
            avg_processing_time = 0
            if completed_jobs_with_time:
                avg_processing_time = sum(job.processing_time for job in completed_jobs_with_time) / len(completed_jobs_with_time)
            
            return {
                "queue_size": len(self.pending_queue),
                "total_jobs": len(self.jobs),
                "status_breakdown": status_counts,
                "priority_breakdown": priority_counts,
                "statistics": {
                    "total_jobs_created": self.total_jobs_created,
                    "total_jobs_completed": self.total_jobs_completed,
                    "total_emails_processed": self.total_emails_processed,
                    "total_emails_failed": self.total_emails_failed,
                    "success_rate": (self.total_jobs_completed / max(1, self.total_jobs_created)) * 100,
                    "email_success_rate": (self.total_emails_processed / max(1, self.total_emails_processed + self.total_emails_failed)) * 100,
                    "average_processing_time_seconds": avg_processing_time
                }
            }
    
    def get_active_jobs(self) -> List[Dict]:
        """Get all currently processing jobs"""
        with self.lock:
            active_jobs = []
            for job in self.processing_jobs.values():
                job_details = self.get_job_details(job.job_id)
                if job_details:
                    active_jobs.append(job_details)
            
            return sorted(active_jobs, key=lambda x: x['started_at'] or '')
    
    def get_pending_jobs(self) -> List[Dict]:
        """Get all pending jobs"""
        with self.lock:
            pending_jobs = []
            for job in self.jobs.values():
                if job.status == JobStatus.PENDING:
                    job_details = self.get_job_details(job.job_id)
                    if job_details:
                        pending_jobs.append(job_details)
            
            return sorted(pending_jobs, key=lambda x: (-job.priority.value, x['created_at']))
    
    def get_recent_completed_jobs(self, limit: int = 20) -> List[Dict]:
        """Get recently completed jobs"""
        with self.lock:
            completed = list(self.completed_jobs.values())
            completed.sort(key=lambda x: x.completed_at or datetime.min, reverse=True)
            
            result = []
            for job in completed[:limit]:
                job_details = self.get_job_details(job.job_id)
                if job_details:
                    result.append(job_details)
            
            return result
    
    def _cleanup_old_completed_jobs(self):
        """Remove old completed jobs to prevent memory bloat"""
        if len(self.completed_jobs) > self.max_completed_jobs:
            # Sort by completion time and keep only the most recent
            completed_list = list(self.completed_jobs.items())
            completed_list.sort(key=lambda x: x[1].completed_at or datetime.min, reverse=True)
            
            # Keep only the most recent jobs
            jobs_to_keep = dict(completed_list[:self.max_completed_jobs])
            jobs_to_remove = set(self.completed_jobs.keys()) - set(jobs_to_keep.keys())
            
            # Remove old jobs
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                del self.completed_jobs[job_id]
            
            if jobs_to_remove:
                print(f"🧹 Cleaned up {len(jobs_to_remove)} old completed jobs")
    
    def clear_completed_jobs(self, older_than_hours: int = 24) -> int:
        """Manually clear completed jobs older than specified hours"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
            jobs_to_remove = []
            
            for job_id, job in self.completed_jobs.items():
                if job.completed_at and job.completed_at < cutoff_time:
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                if job_id in self.jobs:
                    del self.jobs[job_id]
                if job_id in self.completed_jobs:
                    del self.completed_jobs[job_id]
            
            if jobs_to_remove:
                print(f"🧹 Manually cleared {len(jobs_to_remove)} old completed jobs")
            
            return len(jobs_to_remove)
    
    def get_job_results(self, job_id: str, limit: int = None) -> Optional[Dict]:
        """Get results for a specific job"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            
            results = job.results
            errors = job.errors
            
            if limit:
                results = results[-limit:] if results else []
                errors = errors[-limit:] if errors else []
            
            return {
                "job_id": job_id,
                "status": job.status.value,
                "total_results": len(job.results),
                "total_errors": len(job.errors),
                "results": results,
                "errors": errors
            }

# Global instance
_memory_job_queue = None

def get_memory_job_queue() -> MemoryJobQueue:
    """Get or create global memory job queue"""
    global _memory_job_queue
    if _memory_job_queue is None:
        _memory_job_queue = MemoryJobQueue()
    return _memory_job_queue

if __name__ == "__main__":
    print("🚀 Memory Job Queue Test")
    print("=" * 50)
    
    queue = get_memory_job_queue()
    
    # Create test job
    test_emails = ["test1@example.com", "test2@example.com", "test3@example.com"]
    job_id = queue.create_job(test_emails, JobPriority.HIGH)
    
    # Get job status
    status = queue.get_job_details(job_id)
    print(f"Job status: {status}")
    
    # Get queue status
    queue_status = queue.get_queue_status()
    print(f"Queue status: {queue_status}")
