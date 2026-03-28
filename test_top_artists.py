#!/usr/bin/env python3
"""
Quick test script to verify current_user_top_artists() works with updated scopes.

This will help identify if the 403 error is due to:
1. Missing scope (user-top-read)
2. Premium requirement
3. Other API issues
"""

import os
from dotenv import load_dotenv
from spotify_client import get_spotify

load_dotenv()

def test_top_artists():
    """Test if top artists endpoint works."""
    print("=" * 70)
    print("TESTING: current_user_top_artists()")
    print("=" * 70)
    
    try:
        print("\n[1/3] Authenticating with Spotify...")
        sp = get_spotify()
        print("✓ Authentication successful")
        
        print("\n[2/3] Fetching user info to check account type...")
        user = sp.me()
        account_type = user.get('product', 'unknown')
        print(f"✓ Account type: {account_type}")
        print(f"  User: {user.get('display_name', 'N/A')}")
        print(f"  Email: {user.get('email', 'N/A')}")
        
        print("\n[3/3] Calling current_user_top_artists(limit=5)...")
        result = sp.current_user_top_artists(limit=5, time_range='short_term')
        
        print("✓ SUCCESS! Top artists fetched successfully")
        print(f"  Total items: {result.get('total', 0)}")
        print(f"  Items returned: {len(result.get('items', []))}")
        
        if result.get('items'):
            print("\n  Top 5 Artists:")
            for i, artist in enumerate(result['items'], 1):
                print(f"    {i}. {artist['name']}")
        
        print("\n" + "=" * 70)
        print("✅ TEST PASSED - No Premium restriction detected")
        print("=" * 70)
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ERROR: {error_msg}")
        print("\nDiagnostics:")
        print("-" * 70)
        
        # Detect specific error types
        if "403" in error_msg or "Forbidden" in error_msg:
            print("⚠️  HTTP 403 Forbidden detected")
            
            if "premium" in error_msg.lower() or "blocked" in error_msg.lower():
                print("\n🔴 ROOT CAUSE: Premium Subscription Required")
                print("   Your Spotify account needs a Premium subscription")
                print("   to access the top artists endpoint.")
                print("\n   This is expected for free tier users.")
                print("   The main app will gracefully skip this data source.")
            else:
                print("\n🔴 ROOT CAUSE: Missing OAuth Scope")
                print("   The 'user-top-read' scope may not be in your token.")
                print("\n   FIX: Regenerate your token:")
                print("   1. rm .cache")
                print("   2. python main.py")
                print("   3. Reauthorize in browser")
        
        elif "scope" in error_msg.lower() or "permission" in error_msg.lower():
            print("\n🔴 ROOT CAUSE: OAuth Scope Issue")
            print("   Token doesn't have required permissions.")
            print("\n   FIX: Regenerate token with correct scopes:")
            print("   1. rm .cache")
            print("   2. python main.py")
        
        else:
            print("\n⚠️  Unknown error type")
            print("   Full error:", error_msg)
        
        print("=" * 70)
        return False


if __name__ == "__main__":
    test_top_artists()
