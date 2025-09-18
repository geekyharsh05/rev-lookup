#!/usr/bin/env python3
"""
DynamoDB Token Manager for Multi-Token Storage
Manages Bearer tokens with automatic expiry using DynamoDB TTL
"""

import os
import boto3
import time
import threading
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import jwt
from dataclasses import dataclass, asdict
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TokenInfo:
    token_id: str
    token: str
    created_at: datetime
    expires_at: datetime
    daily_usage: int = 0
    total_usage: int = 0
    is_active: bool = True
    last_used: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None

class DynamoTokenManager:
    def __init__(self, 
                 table_name: str = "bearer_tokens",
                 max_daily_requests: int = 500, 
                 token_lifetime_hours: int = 22,
                 aws_access_key_id: str = None,
                 aws_secret_access_key: str = None,
                 region_name: str = "us-east-1"):
        
        self.table_name = table_name
        self.max_daily_requests = max_daily_requests
        self.token_lifetime_hours = token_lifetime_hours
        
        # In-memory cache for fast access
        self.tokens_cache: Dict[str, TokenInfo] = {}
        self.cache_lock = threading.RLock()
        
        # Initialize DynamoDB
        try:
            if aws_access_key_id and aws_secret_access_key:
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    region_name=region_name
                )
            else:
                self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
            
            self.table = self.dynamodb.Table(table_name)
            print(f"✅ Connected to DynamoDB table: {table_name}")
            
        except Exception as e:
            print(f"❌ Failed to connect to DynamoDB: {e}")
            raise
        
        # Create table if it doesn't exist
        self._create_table_if_not_exists()
        
        # Load existing tokens into cache
        self._load_tokens_to_cache()
        
        # Start background sync thread
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        
        # Track daily usage reset
        self.last_usage_reset = datetime.now().date()
        
        print(f"✅ DynamoDB Token Manager initialized with {len(self.tokens_cache)} tokens")
    
    def _create_table_if_not_exists(self):
        """Create DynamoDB table if it doesn't exist"""
        try:
            # Check if table exists
            self.table.load()
            print(f"✅ Table {self.table_name} already exists")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"📝 Creating DynamoDB table: {self.table_name}")
                
                # Create table with TTL enabled
                table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {
                            'AttributeName': 'token_id',
                            'KeyType': 'HASH'  # Partition key
                        }
                    ],
                    AttributeDefinitions=[
                        {
                            'AttributeName': 'token_id',
                            'AttributeType': 'S'
                        }
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
                
                # Wait for table to be created
                print("⏳ Waiting for table to be created...")
                table.wait_until_exists()
                
                # Enable TTL on expires_at field
                try:
                    self.dynamodb.meta.client.update_time_to_live(
                        TableName=self.table_name,
                        TimeToLiveSpecification={
                            'AttributeName': 'ttl',
                            'Enabled': True
                        }
                    )
                    print("✅ TTL enabled on table")
                except Exception as ttl_error:
                    print(f"⚠️  Could not enable TTL: {ttl_error}")
                
                print(f"✅ Table {self.table_name} created successfully")
                
            else:
                print(f"❌ Error checking table: {e}")
                raise
    
    def _generate_token_id(self, token: str) -> str:
        """Generate a unique token ID from token content"""
        # Use hash of token content + timestamp for uniqueness
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        timestamp = int(time.time())
        return f"token_{token_hash}_{timestamp}"
    
    def add_token(self, token: str, token_id: str = None) -> bool:
        """Add a new token to DynamoDB"""
        with self.cache_lock:
            try:
                # Generate token ID if not provided
                if not token_id:
                    token_id = self._generate_token_id(token)
                
                # Check if token already exists in cache
                for existing_token in self.tokens_cache.values():
                    if existing_token.token == token:
                        print(f"⚠️  Token already exists: {existing_token.token_id}")
                        return False
                
                # Create token info
                now = datetime.now()
                expires_at = now + timedelta(hours=self.token_lifetime_hours)
                ttl_timestamp = int(expires_at.timestamp())
                
                token_info = TokenInfo(
                    token_id=token_id,
                    token=token,
                    created_at=now,
                    expires_at=expires_at
                )
                
                # Save to DynamoDB
                item = {
                    'token_id': token_id,
                    'token': token,
                    'created_at': now.isoformat(),
                    'expires_at': expires_at.isoformat(),
                    'ttl': ttl_timestamp,  # DynamoDB TTL field
                    'daily_usage': 0,
                    'total_usage': 0,
                    'is_active': True,
                    'error_count': 0
                }
                
                self.table.put_item(Item=item)
                
                # Add to cache
                self.tokens_cache[token_id] = token_info
                
                print(f"✅ Added token {token_id} to DynamoDB (expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')})")
                return True
                
            except Exception as e:
                print(f"❌ Failed to add token: {e}")
                return False
    
    def add_multiple_tokens(self, tokens: List[str]) -> Dict[str, bool]:
        """Add multiple tokens at once"""
        results = {}
        
        for i, token in enumerate(tokens):
            token_id = f"token_batch_{int(time.time())}_{i}"
            success = self.add_token(token, token_id)
            results[token_id] = success
        
        successful = sum(1 for success in results.values() if success)
        print(f"✅ Added {successful}/{len(tokens)} tokens successfully")
        
        return results
    
    def get_available_token(self) -> Optional[Tuple[str, str]]:
        """Get an available token for use (original method - single use)"""
        with self.cache_lock:
            # Reset daily usage if it's a new day
            self._reset_daily_usage_if_needed()
            
            # Sync with DynamoDB to get latest data
            self._sync_from_dynamodb()
            
            # Find available tokens
            available_tokens = []
            current_time = datetime.now()
            
            for token_id, token_info in self.tokens_cache.items():
                if (token_info.is_active and 
                    token_info.daily_usage < self.max_daily_requests and
                    token_info.expires_at > current_time):
                    
                    # Calculate priority (lower usage = higher priority)
                    priority = token_info.daily_usage + (token_info.error_count * 10)
                    available_tokens.append((priority, token_id, token_info))
            
            if not available_tokens:
                print("⚠️  No available tokens")
                return None
            
            # Sort by priority and get the best token
            available_tokens.sort(key=lambda x: x[0])
            _, token_id, token_info = available_tokens[0]
            
            # Update usage
            token_info.daily_usage += 1
            token_info.total_usage += 1
            token_info.last_used = datetime.now()
            
            # Update in DynamoDB
            self._update_token_in_dynamodb(token_info)
            
            return token_id, token_info.token
    
    def get_rotating_token(self, current_token_id: str = None, requests_per_token: int = 15) -> Optional[Tuple[str, str]]:
        """
        Get a token for rotation-based usage
        
        Args:
            current_token_id: ID of currently used token (if any)
            requests_per_token: How many requests to make with each token before rotating
            
        Returns:
            Tuple of (token_id, token) or None if no tokens available
        """
        with self.cache_lock:
            # Reset daily usage if it's a new day
            self._reset_daily_usage_if_needed()
            
            # Sync with DynamoDB to get latest data
            self._sync_from_dynamodb()
            
            current_time = datetime.now()
            
            # If we have a current token, check if we should keep using it
            if current_token_id and current_token_id in self.tokens_cache:
                current_token = self.tokens_cache[current_token_id]
                
                # Check if current token is still usable and hasn't hit rotation limit
                if (current_token.is_active and 
                    current_token.daily_usage < self.max_daily_requests and
                    current_token.expires_at > current_time):
                    
                    # Calculate how many times we've used this token in current session
                    session_usage = getattr(current_token, 'session_usage', 0)
                    
                    if session_usage < requests_per_token:
                        # Continue using current token
                        current_token.daily_usage += 1
                        current_token.total_usage += 1
                        current_token.last_used = datetime.now()
                        current_token.session_usage = session_usage + 1
                        
                        # Update in DynamoDB
                        self._update_token_in_dynamodb(current_token)
                        
                        print(f"🔄 Continuing with token {current_token_id} (usage: {session_usage + 1}/{requests_per_token})")
                        return current_token_id, current_token.token
                    else:
                        print(f"🔃 Token {current_token_id} reached rotation limit ({requests_per_token}), switching...")
                        # Reset session usage for this token
                        current_token.session_usage = 0
            
            # Find next available token (excluding current one if rotating)
            available_tokens = []
            
            for token_id, token_info in self.tokens_cache.items():
                if (token_info.is_active and 
                    token_info.daily_usage < self.max_daily_requests and
                    token_info.expires_at > current_time and
                    token_id != current_token_id):  # Exclude current token for rotation
                    
                    # Calculate priority (lower usage = higher priority)
                    priority = token_info.daily_usage + (token_info.error_count * 10)
                    # Add slight penalty for recently used tokens to encourage rotation
                    if token_info.last_used and (current_time - token_info.last_used).seconds < 300:  # 5 minutes
                        priority += 5
                    
                    available_tokens.append((priority, token_id, token_info))
            
            # If no other tokens available, try current token again (fallback)
            if not available_tokens and current_token_id and current_token_id in self.tokens_cache:
                current_token = self.tokens_cache[current_token_id]
                if (current_token.is_active and 
                    current_token.daily_usage < self.max_daily_requests and
                    current_token.expires_at > current_time):
                    available_tokens.append((current_token.daily_usage, current_token_id, current_token))
            
            if not available_tokens:
                print("⚠️  No available tokens for rotation")
                return None
            
            # Sort by priority and get the best token
            available_tokens.sort(key=lambda x: x[0])
            _, token_id, token_info = available_tokens[0]
            
            # Update usage and reset session usage for new token
            token_info.daily_usage += 1
            token_info.total_usage += 1
            token_info.last_used = datetime.now()
            token_info.session_usage = 1  # Starting fresh session with this token
            
            # Update in DynamoDB
            self._update_token_in_dynamodb(token_info)
            
            print(f"🆕 Switching to token {token_id} (daily usage: {token_info.daily_usage}/{self.max_daily_requests})")
            return token_id, token_info.token
    
    def mark_token_error(self, token_id: str, error_message: str):
        """Mark a token as having an error"""
        with self.cache_lock:
            if token_id in self.tokens_cache:
                token_info = self.tokens_cache[token_id]
                token_info.error_count += 1
                token_info.last_error = error_message
                
                # Deactivate token if too many errors
                if token_info.error_count >= 5:
                    token_info.is_active = False
                    print(f"❌ Token {token_id} deactivated due to repeated errors")
                
                # Update in DynamoDB
                self._update_token_in_dynamodb(token_info)
    
    def mark_token_success(self, token_id: str):
        """Mark a token as successful (reset error count)"""
        with self.cache_lock:
            if token_id in self.tokens_cache:
                token_info = self.tokens_cache[token_id]
                token_info.error_count = max(0, token_info.error_count - 1)
                if token_info.error_count == 0:
                    token_info.last_error = None
                
                # Update in DynamoDB
                self._update_token_in_dynamodb(token_info)
    
    def _update_token_in_dynamodb(self, token_info: TokenInfo):
        """Update token information in DynamoDB"""
        try:
            update_expression = "SET daily_usage = :daily_usage, total_usage = :total_usage, is_active = :is_active, error_count = :error_count"
            expression_values = {
                ':daily_usage': token_info.daily_usage,
                ':total_usage': token_info.total_usage,
                ':is_active': token_info.is_active,
                ':error_count': token_info.error_count
            }
            
            if token_info.last_used:
                update_expression += ", last_used = :last_used"
                expression_values[':last_used'] = token_info.last_used.isoformat()
            
            if token_info.last_error:
                update_expression += ", last_error = :last_error"
                expression_values[':last_error'] = token_info.last_error
            
            self.table.update_item(
                Key={'token_id': token_info.token_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
        except Exception as e:
            print(f"❌ Failed to update token {token_info.token_id} in DynamoDB: {e}")
    
    def _load_tokens_to_cache(self):
        """Load tokens from DynamoDB to local cache"""
        try:
            response = self.table.scan(
                FilterExpression="attribute_exists(token_id) AND is_active = :active",
                ExpressionAttributeValues={':active': True}
            )
            
            loaded_count = 0
            current_time = datetime.now()
            
            for item in response.get('Items', []):
                try:
                    expires_at = datetime.fromisoformat(item['expires_at'])
                    
                    # Skip expired tokens
                    if expires_at <= current_time:
                        continue
                    
                    token_info = TokenInfo(
                        token_id=item['token_id'],
                        token=item['token'],
                        created_at=datetime.fromisoformat(item['created_at']),
                        expires_at=expires_at,
                        daily_usage=item.get('daily_usage', 0),
                        total_usage=item.get('total_usage', 0),
                        is_active=item.get('is_active', True),
                        last_used=datetime.fromisoformat(item['last_used']) if item.get('last_used') else None,
                        error_count=item.get('error_count', 0),
                        last_error=item.get('last_error')
                    )
                    
                    self.tokens_cache[token_info.token_id] = token_info
                    loaded_count += 1
                    
                except Exception as e:
                    print(f"⚠️  Error loading token {item.get('token_id', 'unknown')}: {e}")
            
            print(f"✅ Loaded {loaded_count} tokens from DynamoDB to cache")
            
        except Exception as e:
            print(f"❌ Failed to load tokens from DynamoDB: {e}")
    
    def _sync_from_dynamodb(self):
        """Sync cache with DynamoDB (lightweight sync)"""
        try:
            # Get only active tokens that might have changed
            response = self.table.scan(
                FilterExpression="is_active = :active",
                ExpressionAttributeValues={':active': True},
                ProjectionExpression="token_id, daily_usage, total_usage, error_count, last_used, last_error"
            )
            
            for item in response.get('Items', []):
                token_id = item['token_id']
                if token_id in self.tokens_cache:
                    token_info = self.tokens_cache[token_id]
                    token_info.daily_usage = item.get('daily_usage', 0)
                    token_info.total_usage = item.get('total_usage', 0)
                    token_info.error_count = item.get('error_count', 0)
                    token_info.last_error = item.get('last_error')
                    
                    if item.get('last_used'):
                        token_info.last_used = datetime.fromisoformat(item['last_used'])
            
        except Exception as e:
            print(f"❌ Sync error: {e}")
    
    def _reset_daily_usage_if_needed(self):
        """Reset daily usage counters if it's a new day"""
        current_date = datetime.now().date()
        if current_date > self.last_usage_reset:
            print(f"🔄 Resetting daily usage counters for {current_date}")
            
            # Reset in cache
            for token_info in self.tokens_cache.values():
                token_info.daily_usage = 0
            
            # Batch update in DynamoDB
            try:
                with self.table.batch_writer() as batch:
                    for token_id in self.tokens_cache.keys():
                        batch.update_item(
                            Key={'token_id': token_id},
                            UpdateExpression="SET daily_usage = :zero",
                            ExpressionAttributeValues={':zero': 0}
                        )
                
                print("✅ Daily usage reset in DynamoDB")
                
            except Exception as e:
                print(f"❌ Failed to reset daily usage in DynamoDB: {e}")
            
            self.last_usage_reset = current_date
    
    def _sync_loop(self):
        """Background sync loop"""
        while True:
            try:
                time.sleep(300)  # Sync every 5 minutes
                with self.cache_lock:
                    self._sync_from_dynamodb()
                    
            except Exception as e:
                print(f"❌ Sync loop error: {e}")
                time.sleep(60)
    
    def get_status(self) -> Dict:
        """Get current status of all tokens"""
        with self.cache_lock:
            total_tokens = len(self.tokens_cache)
            active_tokens = sum(1 for t in self.tokens_cache.values() if t.is_active)
            available_tokens = sum(1 for t in self.tokens_cache.values() 
                                 if t.is_active and t.daily_usage < self.max_daily_requests)
            total_daily_usage = sum(t.daily_usage for t in self.tokens_cache.values())
            
            return {
                "total_tokens": total_tokens,
                "active_tokens": active_tokens,
                "available_tokens": available_tokens,
                "total_daily_usage": total_daily_usage,
                "max_daily_capacity": total_tokens * self.max_daily_requests,
                "available_capacity": sum(max(0, self.max_daily_requests - t.daily_usage) 
                                        for t in self.tokens_cache.values() if t.is_active),
                "usage_percentage": (total_daily_usage / (total_tokens * self.max_daily_requests)) * 100 if total_tokens > 0 else 0,
                "token_details": [
                    {
                        "token_id": token_id,
                        "daily_usage": info.daily_usage,
                        "total_usage": info.total_usage,
                        "is_active": info.is_active,
                        "error_count": info.error_count,
                        "created_at": info.created_at.isoformat(),
                        "expires_at": info.expires_at.isoformat(),
                        "last_used": info.last_used.isoformat() if info.last_used else None,
                        "remaining_usage": max(0, self.max_daily_requests - info.daily_usage),
                        "token_preview": info.token[:50] + "..."
                    }
                    for token_id, info in self.tokens_cache.items()
                ]
            }
    
    def get_available_capacity(self) -> int:
        """Get total remaining request capacity for today"""
        with self.cache_lock:
            return sum(max(0, self.max_daily_requests - t.daily_usage) 
                      for t in self.tokens_cache.values() if t.is_active)
    
    def delete_token(self, token_id: str) -> bool:
        """Manually delete a token"""
        with self.cache_lock:
            try:
                # Remove from DynamoDB
                self.table.delete_item(Key={'token_id': token_id})
                
                # Remove from cache
                if token_id in self.tokens_cache:
                    del self.tokens_cache[token_id]
                
                print(f"🗑️  Deleted token {token_id}")
                return True
                
            except Exception as e:
                print(f"❌ Failed to delete token {token_id}: {e}")
                return False

# Global instance
_dynamo_token_manager = None

def get_dynamo_token_manager() -> DynamoTokenManager:
    """Get or create global DynamoDB token manager"""
    global _dynamo_token_manager
    if _dynamo_token_manager is None:
        # Get AWS credentials from environment
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        _dynamo_token_manager = DynamoTokenManager(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
    return _dynamo_token_manager

def add_token_from_file(file_path: str = "token.txt") -> bool:
    """Add token from token.txt file to DynamoDB (no validation)"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                token = f.read().strip()
            
            if token:
                # Ensure token starts with Bearer if it doesn't already
                if not token.startswith("Bearer "):
                    token = "Bearer " + token
                
                print(f"📄 Adding token from file: {token[:50]}...")
                manager = get_dynamo_token_manager()
                return manager.add_token(token)
        
        print(f"❌ File {file_path} not found or empty")
        return False
        
    except Exception as e:
        print(f"❌ Failed to add token from file: {e}")
        return False

def add_multiple_tokens_from_file(file_path: str = "token.txt") -> dict:
    """Add multiple tokens from token.txt file to DynamoDB
    
    Supports multiple formats:
    1. One token per line
    2. Comma-separated tokens
    3. Space-separated tokens
    4. Mixed format (automatically detects and parses)
    
    Returns dict with success count and details
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File {file_path} not found",
                "tokens_added": 0,
                "tokens_failed": 0,
                "details": []
            }
        
        with open(file_path, 'r') as f:
            content = f.read().strip()
        
        if not content:
            return {
                "success": False,
                "error": "File is empty",
                "tokens_added": 0,
                "tokens_failed": 0,
                "details": []
            }
        
        # Parse tokens from content - support multiple formats
        tokens = parse_tokens_from_content(content)
        
        if not tokens:
            return {
                "success": False,
                "error": "No valid tokens found in file",
                "tokens_added": 0,
                "tokens_failed": 0,
                "details": []
            }
        
        print(f"📄 Found {len(tokens)} tokens in {file_path}")
        
        # Add tokens to DynamoDB
        manager = get_dynamo_token_manager()
        results = {}
        tokens_added = 0
        tokens_failed = 0
        details = []
        
        for i, token in enumerate(tokens, 1):
            # Ensure token starts with Bearer if it doesn't already
            if not token.startswith("Bearer "):
                token = "Bearer " + token
            
            try:
                success = manager.add_token(token)
                token_preview = token[:50] + "..." if len(token) > 50 else token
                
                if success:
                    tokens_added += 1
                    details.append({
                        "token_number": i,
                        "status": "success",
                        "preview": token_preview
                    })
                    print(f"✅ Token {i}/{len(tokens)} added: {token_preview}")
                else:
                    tokens_failed += 1
                    details.append({
                        "token_number": i,
                        "status": "failed",
                        "preview": token_preview,
                        "error": "Failed to add to DynamoDB (may be duplicate or invalid)"
                    })
                    print(f"❌ Token {i}/{len(tokens)} failed: {token_preview}")
                    
            except Exception as e:
                tokens_failed += 1
                token_preview = token[:50] + "..." if len(token) > 50 else token
                details.append({
                    "token_number": i,
                    "status": "failed", 
                    "preview": token_preview,
                    "error": str(e)
                })
                print(f"❌ Token {i}/{len(tokens)} error: {e}")
        
        return {
            "success": tokens_added > 0,
            "message": f"Added {tokens_added}/{len(tokens)} tokens successfully",
            "tokens_added": tokens_added,
            "tokens_failed": tokens_failed,
            "total_tokens": len(tokens),
            "details": details
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to process file: {str(e)}",
            "tokens_added": 0,
            "tokens_failed": 0,
            "details": []
        }

def parse_tokens_from_content(content: str) -> list:
    """Parse tokens from file content supporting multiple formats"""
    tokens = []
    
    # Remove extra whitespace and normalize line endings
    content = content.strip().replace('\r\n', '\n').replace('\r', '\n')
    
    # Try different parsing strategies
    
    # Strategy 1: Line-separated tokens (most common)
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    
    # Check if we have multiple lines, each potentially being a token
    if len(lines) > 1:
        for line in lines:
            # Each line might contain one token or multiple comma/space separated tokens
            line_tokens = parse_single_line_tokens(line)
            tokens.extend(line_tokens)
    else:
        # Strategy 2: Single line with multiple tokens (comma or space separated)
        single_line = lines[0] if lines else content
        tokens.extend(parse_single_line_tokens(single_line))
    
    # Filter out empty tokens and validate basic token format
    valid_tokens = []
    for token in tokens:
        token = token.strip()
        if token and len(token) > 50:  # Bearer tokens are typically very long
            # Remove Bearer prefix if present for consistency (will be re-added later)
            if token.startswith("Bearer "):
                token = token[7:]
            valid_tokens.append(token)
    
    return valid_tokens

def parse_single_line_tokens(line: str) -> list:
    """Parse tokens from a single line (comma or space separated)"""
    tokens = []
    
    # First try comma separation
    if ',' in line:
        parts = [part.strip() for part in line.split(',') if part.strip()]
        for part in parts:
            if len(part) > 50:  # Looks like a token
                tokens.append(part)
    
    # If no comma separation or no valid tokens found, try space separation
    # But be careful - tokens contain spaces, so we need to be smart about this
    elif ' ' in line and not line.startswith('Bearer '):
        # Multiple space-separated tokens (unlikely but possible)
        # This is tricky because Bearer tokens contain spaces
        # We'll split and try to reconstruct valid tokens
        parts = line.split()
        current_token = ""
        
        for part in parts:
            if part == "Bearer" and current_token:
                # Save previous token and start new one
                if len(current_token.strip()) > 50:
                    tokens.append(current_token.strip())
                current_token = "Bearer"
            else:
                current_token += " " + part if current_token else part
        
        # Don't forget the last token
        if current_token and len(current_token.strip()) > 50:
            tokens.append(current_token.strip())
    
    # If no separators found, treat the entire line as one token
    if not tokens and len(line.strip()) > 50:
        tokens.append(line.strip())
    
    return tokens

if __name__ == "__main__":
    print("🚀 DynamoDB Token Manager Test")
    print("=" * 50)
    
    # Test with sample token
    sample_token = "Bearer EwAYBN2CBAAUVyZrnn9xwmQ7VNJefVz4FrT4XAAAAfC3Jy..."
    
    manager = get_dynamo_token_manager()
    
    # Add token
    success = manager.add_token(sample_token)
    print(f"Token added: {success}")
    
    # Get status
    status = manager.get_status()
    print(f"Status: {status}")
    
    # Get available token
    token_data = manager.get_available_token()
    if token_data:
        token_id, token = token_data
        print(f"Got token: {token_id} -> {token[:50]}...")
    else:
        print("No available tokens")
