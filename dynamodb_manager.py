import boto3
from datetime import datetime
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv()

class DynamoDBManager:
    def __init__(self, 
                 aws_access_key_id: str = None,
                 aws_secret_access_key: str = None,
                 region_name: str = "us-east-1",
                 table_name: str = "linkedin_profiles"):
        """
        Initialize DynamoDB manager with credentials and table configuration
        
        Args:
            aws_access_key_id: AWS access key ID (if None, will use environment variables or IAM role)
            aws_secret_access_key: AWS secret access key (if None, will use environment variables or IAM role)
            region_name: AWS region name
            table_name: DynamoDB table name for LinkedIn profiles
        """
        self.table_name = table_name
        self.region_name = region_name
        
        # Initialize DynamoDB client
        try:
            if aws_access_key_id and aws_secret_access_key:
                # Use provided credentials
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    region_name=region_name
                )
                print(f"✅ DynamoDB client initialized with provided credentials")
            else:
                # Use environment variables or IAM role
                self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
                print(f"✅ DynamoDB client initialized with environment/IAM credentials")
            
            self.table = self.dynamodb.Table(table_name)
            print(f"✅ Connected to DynamoDB table: {table_name}")
            
        except NoCredentialsError:
            raise Exception("AWS credentials not found. Please provide credentials or set AWS environment variables.")
        except Exception as e:
            raise Exception(f"Failed to initialize DynamoDB client: {str(e)}")
    
    def create_table_if_not_exists(self) -> bool:
        """
        Create the LinkedIn profiles table if it doesn't exist
        
        Returns:
            bool: True if table exists or was created successfully
        """
        try:
            # Check if table exists
            self.table.load()
            print(f"✅ Table {self.table_name} already exists")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Table doesn't exist, create it
                try:
                    print(f"📝 Creating table {self.table_name}...")
                    
                    table = self.dynamodb.create_table(
                        TableName=self.table_name,
                        KeySchema=[
                            {
                                'AttributeName': 'email',
                                'KeyType': 'HASH'  # Partition key
                            },
                            {
                                'AttributeName': 'timestamp',
                                'KeyType': 'RANGE'  # Sort key
                            }
                        ],
                        AttributeDefinitions=[
                            {
                                'AttributeName': 'email',
                                'AttributeType': 'S'  # String
                            },
                            {
                                'AttributeName': 'timestamp',
                                'AttributeType': 'S'  # String (ISO format)
                            }
                        ],
                        BillingMode='PAY_PER_REQUEST'  # On-demand billing
                    )
                    
                    # Wait for table to be created
                    print("⏳ Waiting for table to be created...")
                    table.wait_until_exists()
                    print(f"✅ Table {self.table_name} created successfully")
                    return True
                    
                except Exception as create_error:
                    print(f"❌ Failed to create table: {create_error}")
                    return False
            else:
                print(f"❌ Error checking table existence: {e}")
                return False
    
    def _delete_existing_profiles(self, email: str) -> int:
        """
        Delete all existing profiles for a given email
        
        Args:
            email: Email address to delete profiles for
            
        Returns:
            int: Number of profiles deleted
        """
        try:
            # Query all items with this email
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(email)
            )
            
            items = response.get('Items', [])
            deleted_count = 0
            
            # Delete each item
            for item in items:
                try:
                    self.table.delete_item(
                        Key={
                            'email': item['email'],
                            'timestamp': item['timestamp']
                        }
                    )
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to delete item for {email} at {item.get('timestamp')}: {e}")
            
            if deleted_count > 0:
                print(f"🗑️  Deleted {deleted_count} existing profile(s) for {email}")
            
            return deleted_count
            
        except Exception as e:
            print(f"❌ Failed to delete existing profiles for {email}: {str(e)}")
            return 0
    
    def save_profile(self, profile_data: Dict[str, Any]) -> bool:
        """
        Save a single LinkedIn profile to DynamoDB
        First deletes any existing profiles for the same email, then saves the new one
        
        Args:
            profile_data: Profile data dictionary containing email, data, timestamp, etc.
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            email = profile_data.get('email')
            if not email:
                print("❌ No email found in profile data")
                return False
            
            # First, delete any existing profiles for this email
            self._delete_existing_profiles(email)
            
            # Prepare item for DynamoDB
            item = {
                'email': email,
                'timestamp': profile_data.get('timestamp', datetime.now().isoformat()),
                'success': profile_data.get('success', True),
                'profile_data': profile_data.get('data', {}),
                'saved_at': datetime.now().isoformat(),
            }
            
            # Add error information if present
            if 'error' in profile_data:
                item['error'] = profile_data['error']
            
            # Add file path if individual file was saved
            if 'saved_to_file' in profile_data:
                item['saved_to_file'] = profile_data['saved_to_file']
            
            # Save to DynamoDB
            self.table.put_item(Item=item)
            print(f"✅ Saved profile for {email} to DynamoDB (replaced any existing)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save profile for {email}: {str(e)}")
            return False
    
    def save_batch_profiles(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save multiple LinkedIn profiles to DynamoDB using batch write
        First deletes any existing profiles for each email, then saves the new ones
        
        Args:
            profiles: List of profile data dictionaries
            
        Returns:
            Dict with success count, error count, and details
        """
        if not profiles:
            return {"success_count": 0, "error_count": 0, "errors": []}
        
        success_count = 0
        error_count = 0
        errors = []
        deleted_count = 0
        
        try:
            # First, collect all unique emails and delete existing profiles
            unique_emails = set()
            for profile in profiles:
                email = profile.get('email')
                if email:
                    unique_emails.add(email)
            
            # Delete existing profiles for all emails
            for email in unique_emails:
                deleted_count += self._delete_existing_profiles(email)
            
            # Use batch_writer for efficient batch operations
            with self.table.batch_writer() as batch:
                for profile in profiles:
                    try:
                        email = profile.get('email')
                        if not email:
                            error_count += 1
                            errors.append({"profile": profile, "error": "No email found"})
                            continue
                        
                        # Prepare item for DynamoDB
                        item = {
                            'email': email,
                            'timestamp': profile.get('timestamp', datetime.now().isoformat()),
                            'success': profile.get('success', True),
                            'profile_data': profile.get('data', {}),
                            'saved_at': datetime.now().isoformat(),
                        }
                        
                        # Add error information if present
                        if 'error' in profile:
                            item['error'] = profile['error']
                        
                        # Add file path if individual file was saved
                        if 'saved_to_file' in profile:
                            item['saved_to_file'] = profile['saved_to_file']
                        
                        # Add to batch
                        batch.put_item(Item=item)
                        success_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        errors.append({
                            "profile": profile,
                            "error": str(e)
                        })
                        print(f"❌ Error preparing profile for batch save: {str(e)}")
            
            print(f"✅ Batch save completed: {success_count} successful, {error_count} errors, {deleted_count} existing profiles deleted")
            
        except Exception as e:
            print(f"❌ Batch save failed: {str(e)}")
            error_count = len(profiles)
            errors.append({"error": f"Batch operation failed: {str(e)}"})
        
        return {
            "success_count": success_count,
            "error_count": error_count,
            "deleted_count": deleted_count,
            "errors": errors,
            "total_profiles": len(profiles)
        }
    
    def get_profile(self, email: str, timestamp: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a LinkedIn profile from DynamoDB
        
        Args:
            email: Email address to look up
            timestamp: Optional timestamp to get specific version
            
        Returns:
            Profile data if found, None otherwise
        """
        try:
            if timestamp:
                # Get specific version
                response = self.table.get_item(
                    Key={
                        'email': email,
                        'timestamp': timestamp
                    }
                )
            else:
                # Get latest version (scan and sort by timestamp)
                response = self.table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(email),
                    ScanIndexForward=False,  # Sort in descending order (newest first)
                    Limit=1
                )
            
            if 'Item' in response:
                return response['Item']
            else:
                return None
                
        except Exception as e:
            print(f"❌ Failed to get profile for {email}: {str(e)}")
            return None

# Global instance
_dynamodb_manager = None

def get_dynamodb_manager() -> Optional[DynamoDBManager]:
    """Get the global DynamoDB manager instance"""
    return _dynamodb_manager

def initialize_dynamodb_manager(aws_access_key_id: str = None,
                               aws_secret_access_key: str = None,
                               region_name: str = "us-east-1",
                               table_name: str = "linkedin_profiles") -> DynamoDBManager:
    """
    Initialize the global DynamoDB manager
    
    Args:
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        region_name: AWS region name
        table_name: DynamoDB table name
        
    Returns:
        DynamoDBManager instance
    """
    global _dynamodb_manager
    
    try:
        _dynamodb_manager = DynamoDBManager(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            table_name=table_name
        )
        
        # Create table if it doesn't exist
        _dynamodb_manager.create_table_if_not_exists()
        
        print("✅ DynamoDB manager initialized successfully")
        return _dynamodb_manager
        
    except Exception as e:
        print(f"❌ Failed to initialize DynamoDB manager: {str(e)}")
        raise e
