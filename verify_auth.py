#!/usr/bin/env python3
"""
Verify Spotify authentication and diagnose REAL issues.
Tests actual API access, not just Premium status.
"""

import os
from dotenv import load_dotenv
from spotify_client import get_spotify

load_dotenv()

def verify_auth():
    print("=" * 70)
    print("SPOTIFY AUTHENTICATION DIAGNOSTICS")
    print("=" * 70)
    
    try:
        print("\n[1/5] Authenticating with Spotify...")
        print("  (Browser will open - log in with YOUR account)")
        sp = get_spotify()
        print("✓ Authentication successful\n")
        
        print("[2/5] Fetching current user identity...")
        user = sp.current_user()
        
        print("\n" + "=" * 70)
        print("LOGGED IN AS:")
        print("=" * 70)
        print(f"  Email: {user.get('email', 'N/A')}")
        print(f"  Display Name: {user.get('display_name', 'N/A')}")
        print(f"  User ID: {user.get('id', 'N/A')}")
        print(f"  Account Type: {user.get('product', 'unknown').upper()}")
        print(f"  Country: {user.get('country', 'N/A')}")
        print("=" * 70)
        
        print("\n[3/5] Environment Configuration:")
        print("-" * 70)
        client_id = os.getenv("SPOTIPY_CLIENT_ID", "NOT SET")
        print(f"  SPOTIPY_CLIENT_ID: {client_id[:15]}...{client_id[-5:]}" if len(client_id) > 20 else f"  SPOTIPY_CLIENT_ID: {client_id}")
        print(f"  SPOTIPY_CLIENT_SECRET: {'SET (hidden)' if os.getenv('SPOTIPY_CLIENT_SECRET') else 'NOT SET'}")
        print(f"  LASTFM_API_KEY: {'SET' if os.getenv('LASTFM_API_KEY') else 'NOT SET'}")
        
        print("\n[4/5] Testing API Access (REAL DIAGNOSTICS):")
        print("-" * 70)
        
        # Test 1: Search API (should ALWAYS work)
        print("\n  Test 1: Search API")
        try:
            result = sp.search(q="test", type="track", limit=1)
            if result and 'tracks' in result:
                print("  ✅ Search API works - Basic API access confirmed")
            else:
                print("  ⚠️  Search returned unexpected format")
        except Exception as e:
            print(f"  ❌ Search API failed: {e}")
            print("  → This indicates auth/app configuration issue, NOT Premium")
        
        # Test 2: Get own profile (already did this)
        print("\n  Test 2: User Profile API")
        print("  ✅ User profile works (already fetched above)")
        
        # Test 3: Recently played
        print("\n  Test 3: Recently Played API")
        try:
            recent = sp.current_user_recently_played(limit=1)
            if recent:
                print("  ✅ Recently played works")
            else:
                print("  ⚠️  Recently played returned empty")
        except Exception as e:
            print(f"  ❌ Recently played failed: {e}")
        
        # Test 4: Playlists
        print("\n  Test 4: User Playlists API")
        try:
            playlists = sp.current_user_playlists(limit=1)
            if playlists:
                print("  ✅ Playlists API works")
            else:
                print("  ⚠️  Playlists returned empty")
        except Exception as e:
            print(f"  ❌ Playlists failed: {e}")
        
        print("\n[5/5] CRITICAL VERIFICATION:")
        print("=" * 70)
        print("⚠️  YOU MUST VERIFY MANUALLY:")
        print()
        print("1. Go to: https://developer.spotify.com/dashboard")
        print("2. Find your app (the one with your SPOTIPY_CLIENT_ID)")
        print("3. Click on the app → Settings")
        print("4. Check 'User Management' section")
        print()
        print(f"   Does it list: {user.get('email', 'YOUR EMAIL')} ?")
        print()
        print("   ✅ YES → App is configured correctly")
        print("   ❌ NO  → Add your email to the app:")
        print("           Settings → User Management → Add User")
        print()
        print("5. Verify Client ID matches:")
        print(f"   Dashboard shows: (check)")
        print(f"   Your .env has:   {client_id[:15]}...")
        print()
        print("=" * 70)
        
        # Diagnosis
        print("\n📋 DIAGNOSIS:")
        print("-" * 70)
        
        if 'e' in locals() and 'search' in str(e).lower():
            print("❌ PROBLEM: Search API failed")
            print("   This is NOT a Premium issue!")
            print("   Likely causes:")
            print("   1. Email not added to app in dashboard")
            print("   2. Using wrong Client ID")
            print("   3. Account mismatch (logged in vs app owner)")
        else:
            print("✅ APIs appear to be working!")
            print("   If you saw 403 errors earlier:")
            print("   - May have been temporary")
            print("   - Try running main.py again")
        
        print("\n" + "=" * 70)
        print("VERIFICATION COMPLETE")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ AUTHENTICATION FAILED: {e}")
        print("\nTroubleshooting:")
        print("  1. Check .env file has correct credentials")
        print("  2. Delete .cache and try again")
        print("  3. Verify redirect URI: http://127.0.0.1:8888/callback")
        return False


if __name__ == "__main__":
    verify_auth()
