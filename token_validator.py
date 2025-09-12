#!/usr/bin/env python3
"""
Token Validator
Test if a Bearer token is working by making a request to the loki.delve API
"""

import os
import sys
import json
import asyncio
import aiohttp
import uuid

async def validate_token(token):
    """Validate a Bearer token by making a test request to loki.delve API"""
    
    if not token:
        return False, "No token provided"
    
    if not token.startswith('Bearer '):
        token = 'Bearer ' + token
    
    # Generate correlation IDs like the real API does
    def generate_correlation_id():
        return str(uuid.uuid4())
    
    # Test email
    test_email = "test@example.com"
    encoded_email = test_email.replace('@', '%40')
    
    root_correlation_id = generate_correlation_id()
    correlation_id = generate_correlation_id()
    client_correlation_id = generate_correlation_id()
    
    url = f"https://nam.loki.delve.office.com/api/v2/linkedin/profiles?smtp={encoded_email}&personaType=User&displayName={encoded_email}&RootCorrelationId={root_correlation_id}&CorrelationId={correlation_id}&ClientCorrelationId={client_correlation_id}&ConvertGetPost=true"
    
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
        'authorization': token,
        'X-HostAppRing': 'WW',
        'X-HostAppVersion': '20250704003.08',
        'X-HostAppCapabilities': '{"isLokiContactDataDisabled":false,"isOnePersonViewEnabled":false,"isOnePersonContextualViewEnabled":false,"isMsalAuthEnabled":true}',
        'X-AccountLinkedIn3S': 'false',
        'X-Client-Language': 'en-US'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={}) as response:
                status = response.status
                response_text = await response.text()
                
                print(f"🌐 Request to: {url[:80]}...")
                print(f"📊 Response status: {status}")
                
                if status == 200:
                    try:
                        response_json = json.loads(response_text)
                        return True, f"✅ Token is valid! Response: {json.dumps(response_json, indent=2)}"
                    except json.JSONDecodeError:
                        return True, f"✅ Token is valid! Response (non-JSON): {response_text[:200]}..."
                        
                elif status == 401:
                    return False, f"❌ Token is invalid or expired (401 Unauthorized)"
                    
                elif status == 403:
                    return False, f"❌ Token is valid but access is forbidden (403 Forbidden)"
                    
                else:
                    return False, f"❌ Request failed with status {status}: {response_text[:200]}..."
                    
    except aiohttp.ClientError as e:
        return False, f"❌ Network error: {e}"
    except Exception as e:
        return False, f"❌ Unexpected error: {e}"

def main():
    """Main function to validate token"""
    print("🧪 Bearer Token Validator")
    print("=" * 40)
    
    # Check if token is provided as argument
    if len(sys.argv) > 1:
        token = ' '.join(sys.argv[1:])  # Join all args in case token has spaces
        print("📥 Using token from command line argument")
    else:
        # Try to read from token.txt
        token_file = "token.txt"
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    token = f.read().strip()
                
                if token:
                    print("📄 Using token from token.txt")
                else:
                    print("❌ token.txt exists but is empty")
                    print("Usage: python token_validator.py [token]")
                    print("   or: put token in token.txt file")
                    return False
            except Exception as e:
                print(f"❌ Error reading token.txt: {e}")
                return False
        else:
            print("❌ No token.txt file found and no token provided")
            print("Usage: python token_validator.py [token]")
            print("   or: put token in token.txt file")
            return False
    
    # Show token info
    print(f"🔍 Token info:")
    print(f"   Length: {len(token)} characters")
    print(f"   Starts with 'Bearer': {token.startswith('Bearer ')}")
    print(f"   Preview: {token[:50]}...")
    
    # Validate token
    print(f"\n🚀 Testing token with loki.delve API...")
    
    # Run async validation
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_valid, message = loop.run_until_complete(validate_token(token))
        
        print(f"\n📊 Validation Result:")
        print(message)
        
        if is_valid:
            print(f"\n✅ SUCCESS! Your token is working correctly.")
            print(f"   You can now use this token with your API server.")
            return True
        else:
            print(f"\n❌ FAILED! Token validation failed.")
            print(f"   You may need to extract a fresh token.")
            return False
            
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
