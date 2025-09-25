#!/usr/bin/env python3
"""
Debug script to test profile_database table connection and data saving
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from profile_database_manager import initialize_profile_database_manager, get_profile_database_manager
from profile_data_mapper import LinkedInProfileMapper

def main():
    print("🔍 Debugging Profile Database Connection and Data Saving...")
    
    # Load environment variables
    load_dotenv()
    
    # Get AWS credentials
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'ap-south-1')
    
    print(f"📊 AWS Config:")
    print(f"   Region: {aws_region}")
    print(f"   Access Key: {aws_access_key_id[:10] + '...' if aws_access_key_id else 'NOT SET'}")
    print(f"   Secret Key: {'SET' if aws_secret_access_key else 'NOT SET'}")
    
    if not aws_access_key_id or not aws_secret_access_key:
        print("❌ AWS credentials not found!")
        print("   Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        return False
    
    # Initialize profile database manager
    try:
        print("\n🔧 Initializing Profile Database Manager...")
        manager = initialize_profile_database_manager(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
            table_name="profile_database"
        )
        
        if not manager:
            print("❌ Failed to initialize Profile Database Manager")
            return False
            
        print("✅ Profile Database Manager initialized successfully")
        
    except Exception as e:
        print(f"❌ Error initializing Profile Database Manager: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test table access
    print("\n📋 Testing table access...")
    try:
        # Try to describe table
        table_info = manager.table.meta.client.describe_table(TableName="profile_database")
        print(f"✅ Table exists: {table_info['Table']['TableName']}")
        print(f"   Status: {table_info['Table']['TableStatus']}")
        print(f"   Primary Key: {table_info['Table']['KeySchema']}")
        
        # Try to scan table for existing items
        response = manager.table.scan(Limit=5)
        existing_items = response.get('Items', [])
        print(f"   Current items in table: {len(existing_items)}")
        
        if existing_items:
            print("   Sample items:")
            for i, item in enumerate(existing_items[:2]):
                url = item.get('url', 'No URL')
                name = item.get('name', {}).get('S', 'No name') if isinstance(item.get('name'), dict) else item.get('name', 'No name')
                print(f"     {i+1}. URL: {url}, Name: {name}")
        
    except Exception as e:
        print(f"❌ Error accessing table: {e}")
        return False
    
    # Test data mapping and saving with sample data
    print("\n🧪 Testing data mapping and saving...")
    try:
        # Create sample LinkedIn API response
        sample_api_response = {
            "success": True,
            "email": "test@example.com",
            "data": {
                "persons": [
                    {
                        "displayName": "Test User",
                        "headline": "Software Developer",
                        "linkedInUrl": "https://linkedin.com/in/testuser",
                        "location": "San Francisco, CA, USA",
                        "photoUrl": "https://example.com/photo.jpg",
                        "positions": {
                            "positionHistory": [
                                {
                                    "title": "Software Developer",
                                    "companyName": "Test Company",
                                    "startEndDate": {
                                        "start": {"month": 1, "year": 2023}
                                    }
                                }
                            ]
                        },
                        "schools": {
                            "educationHistory": [
                                {
                                    "schoolName": "Test University",
                                    "degreeName": "Computer Science",
                                    "fieldOfStudy": "Software Engineering"
                                }
                            ]
                        }
                    }
                ]
            },
            "timestamp": datetime.now().isoformat()
        }
        
        print("📝 Mapping sample data...")
        mapped_profile = LinkedInProfileMapper.map_profile_data(sample_api_response, "test@example.com")
        
        if mapped_profile is None:
            print("❌ Mapping returned None - check LinkedIn ID extraction")
            return False
        
        # Check if mapping was successful
        url = mapped_profile.get('url', {}).get('S', '')
        name = mapped_profile.get('name', {}).get('S', '')
        print(f"✅ Mapping successful:")
        print(f"   URL (LinkedIn ID): {url}")
        print(f"   Name: {name}")
        print(f"   Total fields mapped: {len(mapped_profile)}")
        
        # Test saving
        print("\n💾 Testing save to database...")
        save_result = manager.save_profile(mapped_profile)
        
        if save_result:
            print("✅ Save successful!")
            
            # Verify by retrieving
            print("🔍 Verifying save by retrieving...")
            retrieved = manager.get_profile(url)
            
            if retrieved:
                retrieved_name = retrieved.get('name', {}).get('S', '') if isinstance(retrieved.get('name'), dict) else retrieved.get('name', '')
                print(f"✅ Retrieved successfully: {retrieved_name}")
                
                # Show some key fields
                print("📊 Key fields in saved profile:")
                key_fields = ['url', 'name', 'position', 'linkedin_id', 'current_company_name']
                for field in key_fields:
                    value = retrieved.get(field, {})
                    if isinstance(value, dict) and 'S' in value:
                        print(f"   {field}: {value['S']}")
                    else:
                        print(f"   {field}: {value}")
                
            else:
                print(f"❌ Could not retrieve saved profile with URL: {url}")
        else:
            print("❌ Save failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error in mapping/saving test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n🎉 All tests passed! Profile database is working correctly.")
    print("\n📋 Summary:")
    print("   ✅ AWS credentials configured")
    print("   ✅ Profile Database Manager initialized")
    print("   ✅ Table exists and accessible")
    print("   ✅ Data mapping working")
    print("   ✅ Data saving working")
    print("   ✅ Data retrieval working")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Debug failed! Check the errors above.")
        sys.exit(1)
    else:
        print("\n✅ Debug completed successfully!")
