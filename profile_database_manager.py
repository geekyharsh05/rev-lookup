import boto3
from datetime import datetime
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv()

class ProfileDatabaseManager:
    def __init__(self, 
                 aws_access_key_id: str = None,
                 aws_secret_access_key: str = None,
                 region_name: str = "ap-south-1",
                 table_name: str = "profile_database"):
        """
        Initialize Profile Database manager with credentials and table configuration
        
        Args:
            aws_access_key_id: AWS access key ID (if None, will use environment variables or IAM role)
            aws_secret_access_key: AWS secret access key (if None, will use environment variables or IAM role)
            region_name: AWS region name
            table_name: DynamoDB table name for profile database
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
                print(f"✅ Profile Database client initialized with provided credentials")
            else:
                # Use environment variables or IAM role
                self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
                print(f"✅ Profile Database client initialized with environment/IAM credentials")
            
            self.table = self.dynamodb.Table(table_name)
            print(f"✅ Connected to Profile Database table: {table_name}")
            
        except NoCredentialsError:
            raise Exception("AWS credentials not found. Please provide credentials or set AWS environment variables.")
        except Exception as e:
            raise Exception(f"Failed to initialize Profile Database client: {str(e)}")
    
    def create_table_if_not_exists(self) -> bool:
        """
        Create the profile_database table if it doesn't exist
        
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
                                'AttributeName': 'url',
                                'KeyType': 'HASH'  # Partition key
                            }
                        ],
                        AttributeDefinitions=[
                            {
                                'AttributeName': 'url',
                                'AttributeType': 'S'  # String
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
    
    def save_profile(self, mapped_profile: Dict[str, Any]) -> bool:
        """
        Save a mapped LinkedIn profile to profile_database table
        
        Args:
            mapped_profile: Mapped profile data in DynamoDB format
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            profile_url = mapped_profile.get('url', {}).get('S', '')
            if not profile_url:
                print("❌ No profile URL found in mapped profile data")
                print(f"🔍 Mapped profile keys: {list(mapped_profile.keys())}")
                return False
            
            print(f"🔄 Converting profile {profile_url} from DynamoDB to native format...")
            
            # Convert DynamoDB format to native Python format
            native_item = self._convert_dynamodb_to_native(mapped_profile)
            
            print(f"🔍 Native item keys: {list(native_item.keys())}")
            print(f"🔍 Native item url: {native_item.get('url', 'NOT FOUND')}")
            print(f"🔍 Native item name: {native_item.get('name', 'NOT FOUND')}")
            
            # Save to DynamoDB
            print(f"💾 Putting item to table {self.table_name}...")
            self.table.put_item(Item=native_item)
            print(f"✅ Saved mapped profile to profile_database: {profile_url}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save profile to profile_database: {str(e)}")
            import traceback
            print("🔍 Full traceback:")
            traceback.print_exc()
            return False
    
    def save_batch_profiles(self, mapped_profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save multiple mapped LinkedIn profiles to profile_database table using batch write
        
        Args:
            mapped_profiles: List of mapped profile data dictionaries
            
        Returns:
            Dict with success count, error count, and details
        """
        if not mapped_profiles:
            return {"success_count": 0, "error_count": 0, "errors": []}
        
        success_count = 0
        error_count = 0
        errors = []
        
        try:
            # Use batch_writer for efficient batch operations
            with self.table.batch_writer() as batch:
                for mapped_profile in mapped_profiles:
                    try:
                        profile_url = mapped_profile.get('url', {}).get('S', '')
                        if not profile_url:
                            error_count += 1
                            errors.append({"profile": mapped_profile, "error": "No profile URL found"})
                            continue
                        
                        # Convert DynamoDB format to native Python format
                        native_item = self._convert_dynamodb_to_native(mapped_profile)
                        
                        # Add to batch
                        batch.put_item(Item=native_item)
                        success_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        errors.append({
                            "profile": mapped_profile,
                            "error": str(e)
                        })
                        print(f"❌ Error preparing mapped profile for batch save: {str(e)}")
            
            print(f"✅ Profile database batch save completed: {success_count} successful, {error_count} errors")
            
        except Exception as e:
            print(f"❌ Profile database batch save failed: {str(e)}")
            error_count = len(mapped_profiles)
            errors.append({"error": f"Batch operation failed: {str(e)}"})
        
        return {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "total_profiles": len(mapped_profiles)
        }
    
    def get_profile(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """
        Get a profile from profile_database table
        
        Args:
            profile_url: Profile URL (LinkedIn ID) to look up
            
        Returns:
            Profile data if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={'url': profile_url}
            )
            
            if 'Item' in response:
                return response['Item']
            else:
                return None
                
        except Exception as e:
            print(f"❌ Failed to get profile for {profile_url}: {str(e)}")
            return None
    
    def list_profiles_paginated(self, limit: int = 10, start_key: str = None) -> tuple:
        """List profiles with pagination"""
        try:
            scan_kwargs = {
                'Limit': limit,
                'ProjectionExpression': 'url, #name, position, linkedin_id, #timestamp, current_company_name, avatar',
                'ExpressionAttributeNames': {
                    '#name': 'name',
                    '#timestamp': 'timestamp'
                }
            }
            
            if start_key:
                scan_kwargs['ExclusiveStartKey'] = {'url': start_key}
            
            response = self.table.scan(**scan_kwargs)
            
            items = response.get('Items', [])
            next_key = response.get('LastEvaluatedKey', {}).get('url') if 'LastEvaluatedKey' in response else None
            
            return items, next_key
        except Exception as e:
            print(f"❌ Error listing profiles: {e}")
            return [], None

    def scan_profiles_by_attributes(self, attributes: Dict) -> List[Dict]:
        """Scan profiles by attributes (expensive operation, use carefully)"""
        try:
            filter_expressions = []
            expression_values = {}
            expression_names = {}
            
            for key, value in attributes.items():
                if value:  # Only add non-empty values
                    if key == 'name':
                        filter_expressions.append("contains(#name, :name_val)")
                        expression_names['#name'] = 'name'
                        expression_values[':name_val'] = value
                    elif key == 'current_company_name':
                        filter_expressions.append("contains(current_company_name, :company_val)")
                        expression_values[':company_val'] = value
            
            if not filter_expressions:
                return []
            
            scan_kwargs = {
                'FilterExpression': ' AND '.join(filter_expressions),
                'ExpressionAttributeValues': expression_values,
                'Limit': 20  # Limit scan results
            }
            
            if expression_names:
                scan_kwargs['ExpressionAttributeNames'] = expression_names
            
            response = self.table.scan(**scan_kwargs)
            return response.get('Items', [])
            
        except Exception as e:
            print(f"❌ Error scanning profiles: {e}")
            return []
    
    def _convert_dynamodb_to_native(self, dynamo_item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB format to native Python format for put_item"""
        native_item = {}
        
        for key, value in dynamo_item.items():
            if isinstance(value, dict):
                if 'S' in value:  # String
                    # Handle empty strings properly
                    native_item[key] = value['S'] if value['S'] else ""
                elif 'N' in value:  # Number
                    try:
                        native_item[key] = int(value['N'])
                    except ValueError:
                        native_item[key] = float(value['N'])
                elif 'BOOL' in value:  # Boolean
                    native_item[key] = value['BOOL']
                elif 'L' in value:  # List
                    native_item[key] = [self._convert_dynamodb_value(item) for item in value['L']]
                elif 'M' in value:  # Map
                    native_item[key] = self._convert_dynamodb_to_native(value['M'])
                else:
                    # Unknown format, keep as is
                    native_item[key] = value
            else:
                # Already native format
                native_item[key] = value
        
        return native_item
    
    def _convert_dynamodb_value(self, value: Any) -> Any:
        """Convert a single DynamoDB value to native Python format"""
        if isinstance(value, dict):
            if 'S' in value:
                return value['S']
            elif 'N' in value:
                try:
                    return int(value['N'])
                except ValueError:
                    return float(value['N'])
            elif 'BOOL' in value:
                return value['BOOL']
            elif 'L' in value:
                return [self._convert_dynamodb_value(item) for item in value['L']]
            elif 'M' in value:
                return self._convert_dynamodb_to_native(value['M'])
        
        return value

# Global instance
_profile_database_manager = None

def get_profile_database_manager() -> Optional[ProfileDatabaseManager]:
    """Get the global Profile Database manager instance"""
    return _profile_database_manager

def initialize_profile_database_manager(aws_access_key_id: str = None,
                                       aws_secret_access_key: str = None,
                                       region_name: str = "ap-south-1",
                                       table_name: str = "profile_database") -> ProfileDatabaseManager:
    """
    Initialize the global Profile Database manager
    
    Args:
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        region_name: AWS region name
        table_name: DynamoDB table name
        
    Returns:
        ProfileDatabaseManager instance
    """
    global _profile_database_manager
    
    try:
        _profile_database_manager = ProfileDatabaseManager(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            table_name=table_name
        )
        
        # Create table if it doesn't exist
        _profile_database_manager.create_table_if_not_exists()
        
        print("✅ Profile Database manager initialized successfully")
        return _profile_database_manager
        
    except Exception as e:
        print(f"❌ Failed to initialize Profile Database manager: {str(e)}")
        raise e

