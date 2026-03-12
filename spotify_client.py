import os
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


def _load_token_from_env():
    """
    Load Spotify token from SPOTIFY_CACHE_JSON environment variable.
    
    This is used in CI/CD environments where the token is passed as a JSON string.
    
    Returns:
        dict: Token info if found, None otherwise
    """
    cache_json = os.getenv("SPOTIFY_CACHE_JSON")
    if not cache_json:
        return None
    
    try:
        token_info = json.loads(cache_json)
        logger.debug("Loaded Spotify token from SPOTIFY_CACHE_JSON environment variable")
        return token_info
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to decode SPOTIFY_CACHE_JSON: {e}")
        return None


def get_spotify():
    """
    Initialize and return an authenticated Spotipy client using OAuth.
    
    Loads SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI 
    from environment variables (typically set in .env file via python-dotenv).
    
    In local environments, uses cached token from .cache file. On first run or
    token expiry, requires browser authorization.
    
    In CI/CD environments (GitHub Actions, etc.):
    - Expects SPOTIFY_CACHE_JSON environment variable containing the serialized token
    - Does not open a browser
    - Raises RuntimeError if token is unavailable
    
    Returns:
        spotipy.Spotify: Authenticated Spotify client instance with user access
    
    Raises:
        RuntimeError: If required credentials are missing or token unavailable in CI
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
    
    # Detect CI/CD environment (GitHub Actions, etc.)
    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    
    if is_ci:
        # In CI: Load token from environment variable
        cache_path = None
        token_info = _load_token_from_env()
        if not token_info:
            raise RuntimeError(
                "No Spotify OAuth token found in CI environment. "
                "Set the SPOTIFY_CACHE_JSON environment variable with the cached token JSON. "
                "See SPOTIFY_SETUP.md for instructions on storing tokens as GitHub Secrets."
            )
    else:
        # In local environment: Use .cache file
        cache_path = ".cache"
        token_info = None
    
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(scope),
        open_browser=not is_ci,
        show_dialog=False,
        cache_path=cache_path
    )
    
    # In CI, inject the token info directly into the auth manager
    if is_ci and token_info:
        auth_manager.cache_handler.save_token_to_cache(token_info)
    
    return spotipy.Spotify(auth_manager=auth_manager)
