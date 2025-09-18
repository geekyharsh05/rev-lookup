#!/usr/bin/env python3
"""
Multi-Token Utility for Managing Multiple Bearer Tokens
Allows adding multiple tokens from token.txt file using various formats
"""

import sys
import os
import argparse
from dynamo_token_manager import add_multiple_tokens_from_file, get_dynamo_token_manager

def display_current_tokens():
    """Display current tokens in DynamoDB"""
    try:
        manager = get_dynamo_token_manager()
        status = manager.get_status()
        
        print("\n📊 Current Token Status:")
        print("=" * 50)
        print(f"Total Tokens: {status['total_tokens']}")
        print(f"Available Tokens: {status['available_tokens']}")
        print(f"Tokens in Cooldown: {status['tokens_in_cooldown']}")
        print(f"Failed Tokens: {status['failed_tokens']}")
        
        if status['total_tokens'] > 0:
            print("\n🔑 Token Details:")
            tokens = manager.get_all_tokens()
            for i, (token_id, token_info) in enumerate(tokens.items(), 1):
                status_emoji = "✅" if token_info.get('available', True) else "❌"
                preview = token_info.get('token', '')[:50] + "..." if len(token_info.get('token', '')) > 50 else token_info.get('token', '')
                print(f"  {status_emoji} Token {i}: {token_id} - {preview}")
        
        return True
    except Exception as e:
        print(f"❌ Error getting token status: {e}")
        return False

def add_tokens_from_file(file_path="token.txt"):
    """Add multiple tokens from file"""
    print(f"\n🔄 Processing tokens from {file_path}...")
    
    if not os.path.exists(file_path):
        print(f"❌ File {file_path} not found")
        return False
    
    # Show file content preview
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
        
        lines = content.split('\n')
        print(f"📄 File contains {len(lines)} line(s)")
        
        # Show preview of content (first 100 chars of each line)
        for i, line in enumerate(lines[:3], 1):  # Show first 3 lines max
            preview = line[:100] + "..." if len(line) > 100 else line
            print(f"   Line {i}: {preview}")
        
        if len(lines) > 3:
            print(f"   ... and {len(lines) - 3} more lines")
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    # Process the tokens
    result = add_multiple_tokens_from_file(file_path)
    
    print(f"\n📊 Results:")
    print("=" * 50)
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"Message: {result['message']}")
        print(f"Tokens Added: {result['tokens_added']}")
        print(f"Tokens Failed: {result['tokens_failed']}")
        print(f"Total Processed: {result['total_tokens']}")
        
        # Show details
        if result['details']:
            print("\n📋 Detailed Results:")
            for detail in result['details']:
                status_emoji = "✅" if detail['status'] == 'success' else "❌"
                error_info = f" - {detail.get('error', '')}" if detail['status'] == 'failed' else ""
                print(f"  {status_emoji} Token {detail['token_number']}: {detail['preview']}{error_info}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    return result['success']

def create_sample_token_file():
    """Create a sample token.txt file with multiple tokens"""
    sample_content = """Bearer EwAIA61DAAAUGik12345abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890

Bearer EwAIA61DAAAUGik67890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890

Bearer EwAIA61DAAAUGikABCDEFabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"""
    
    try:
        with open("sample_tokens.txt", "w") as f:
            f.write(sample_content)
        print("✅ Created sample_tokens.txt with 3 sample tokens")
        print("   You can use this file to test the multi-token functionality")
        print("   Usage: python multi_token_utility.py --add --file sample_tokens.txt")
        return True
    except Exception as e:
        print(f"❌ Error creating sample file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Multi-Token Utility for Managing Bearer Tokens")
    parser.add_argument("--add", action="store_true", help="Add tokens from file")
    parser.add_argument("--status", action="store_true", help="Show current token status")
    parser.add_argument("--file", default="token.txt", help="Token file path (default: token.txt)")
    parser.add_argument("--create-sample", action="store_true", help="Create sample token file")
    
    args = parser.parse_args()
    
    print("🚀 Multi-Token Utility")
    print("=" * 50)
    
    if args.create_sample:
        create_sample_token_file()
        return
    
    if args.status or (not args.add and not args.create_sample):
        display_current_tokens()
    
    if args.add:
        add_tokens_from_file(args.file)
        print("\n📊 Updated Status:")
        display_current_tokens()

if __name__ == "__main__":
    main()

