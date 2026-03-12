import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


def get_spotify():
    """
    Initialize and return an authenticated Spotipy client using OAuth.
    
    Loads SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI 
    from environment variables (typically set in .env file via python-dotenv).
    
    Uses cached token if available. On first run or token expiry, requires
    browser authorization which opens automatically (if a browser is available).
    In headless environments (e.g., GitHub Actions), uses cached token without
    opening a browser.
    
    Returns:
        spotipy.Spotify: Authenticated Spotify client instance with user access
    
    Raises:
        RuntimeError: If required credentials are missing or cached token unavailable in CI
    """
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
    
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Spotify credentials. Ensure SPOTIPY_CLIENT_ID and "
            "SPOTIPY_CLIENT_SECRET are set in .env file or environment variables."
        )
    
    scope = [
        "user-read-recently-played",
        "playlist-modify-private",
        "playlist-modify-public",
        "user-library-read",
    ]
    
    # Detect CI/CD environment (GitHub Actions)
    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(scope),
        open_browser=not is_ci,
        show_dialog=False,
        cache_path=".cache"
    )
    
    return spotipy.Spotify(auth_manager=auth_manager)
