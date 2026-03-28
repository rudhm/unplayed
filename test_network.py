import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sys

print("1. Initializing Spotify client...")
try:
    # This uses your existing .env variables automatically
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth())
except Exception as e:
    print(f"❌ Auth Initialization Failed: {e}")
    sys.exit(1)

print("2. Testing outbound network connection to Spotify API (Port 443)...")
try:
    # We are testing the exact endpoint that crashed your main script
    result = sp.search(q="artist:illenium track:good things fall apart", limit=1)
    
    track_name = result['tracks']['items'][0]['name']
    print("✅ SUCCESS! Network routing and authentication are perfectly clear.")
    print(f"   Test resolved to: {track_name}")
    
except Exception as e:
    print("\n❌ NETWORK OR API FAILURE:")
    print(e)
    print("\nDIAGNOSIS:")
    print("If this says 'Connection refused', Python is actively being blocked")
    print("from reaching the internet by your OS, firewall, or a ghost proxy.")
