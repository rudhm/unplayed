import os
import logging
import requests
import time
from functools import wraps
from typing import List, Dict, Optional

from utils import normalize_text

logger = logging.getLogger(__name__)

LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"


def retry_with_backoff(max_retries=3, base_delay=1):
    """Retry decorator with exponential backoff for API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        retry_after = int(e.response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                        logger.warning(f"Rate limited. Sleeping for {retry_after}s")
                        time.sleep(retry_after)
                    else:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"HTTP error in {func.__name__}: {e}. Retrying in {delay}s")
                            time.sleep(delay)
                        else:
                            raise
                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Error in {func.__name__}: {e}. Retrying in {delay}s")
                        time.sleep(delay)
                    else:
                        raise
            raise Exception(f"Max retries exceeded for {func.__name__}")
        return wrapper
    return decorator


class LastFmClient:
    """
    Last.fm API client for music discovery.
    
    This is the PRIMARY data source for recommendations.
    Provides methods for:
    - Fetching user's top artists
    - Finding similar artists
    - Getting artist's top tracks
    - Fetching track metadata
    """
    
    def __init__(self, api_key: str, username: Optional[str] = None):
        """
        Initialize Last.fm client.
        
        Args:
            api_key: Last.fm API key (required)
            username: Last.fm username (optional, needed for user-specific data)
        """
        if not api_key:
            raise ValueError("Last.fm API key is required")
        
        self.api_key = api_key
        self.username = username
        self.session = requests.Session()
        self.cache = {}
        
        logger.info(f"Initialized Last.fm client (username: {username or 'anonymous'})")
    
    @retry_with_backoff(max_retries=3, base_delay=1)
    def _make_request(self, method: str, params: Dict) -> Dict:
        """
        Make a request to Last.fm API with caching.
        
        Args:
            method: Last.fm API method (e.g., 'user.getTopArtists')
            params: Additional parameters
        
        Returns:
            API response as dict
        """
        cache_key = f"{method}:{str(sorted(params.items()))}"
        
        if cache_key in self.cache:
            logger.debug(f"Cache hit for {method}")
            return self.cache[cache_key]
        
        request_params = {
            'method': method,
            'api_key': self.api_key,
            'format': 'json',
            **params
        }
        
        try:
            response = self.session.get(LASTFM_API_BASE, params=request_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"Last.fm API error: {error_msg}")
                raise Exception(f"Last.fm API error: {error_msg}")
            
            self.cache[cache_key] = data
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for method {method}: {e}")
            raise
    
    def get_user_top_artists(self, period: str = "overall", limit: int = 50) -> List[Dict]:
        """
        Get user's top artists from Last.fm.
        
        Args:
            period: Time period ('overall', '7day', '1month', '3month', '6month', '12month')
            limit: Number of artists to return (max 1000)
        
        Returns:
            List of artist dicts with standardized format:
            {
                'artist': str (normalized name),
                'playcount': int,
                'mbid': str,
                'url': str
            }
        """
        if not self.username:
            logger.warning("No username configured, cannot fetch user top artists")
            return []
        
        try:
            data = self._make_request('user.gettopartists', {
                'user': self.username,
                'period': period,
                'limit': limit
            })
            
            artists = data.get('topartists', {}).get('artist', [])
            
            if isinstance(artists, dict):
                artists = [artists]
            
            result = []
            for artist in artists:
                name = artist.get('name', '')
                if name:
                    result.append({
                        'artist': normalize_text(name),
                        'artist_display': name,
                        'playcount': int(artist.get('playcount', 0)),
                        'mbid': artist.get('mbid', ''),
                        'url': artist.get('url', '')
                    })
            
            logger.info(f"Fetched {len(result)} top artists for user {self.username}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch top artists: {e}")
            return []
    
    def get_similar_artists(self, artist_name: str, limit: int = 30) -> List[Dict]:
        """
        Get artists similar to the given artist.
        
        Args:
            artist_name: Name of the artist
            limit: Number of similar artists to return (max 100)
        
        Returns:
            List of artist dicts with standardized format:
            {
                'artist': str (normalized name),
                'match': float (similarity score 0-1),
                'mbid': str,
                'url': str
            }
        """
        try:
            data = self._make_request('artist.getsimilar', {
                'artist': artist_name,
                'limit': limit
            })
            
            similar = data.get('similarartists', {}).get('artist', [])
            
            if isinstance(similar, dict):
                similar = [similar]
            
            result = []
            for artist in similar:
                name = artist.get('name', '')
                if name:
                    result.append({
                        'artist': normalize_text(name),
                        'artist_display': name,
                        'match': float(artist.get('match', 0)),
                        'mbid': artist.get('mbid', ''),
                        'url': artist.get('url', '')
                    })
            
            logger.debug(f"Found {len(result)} similar artists to {artist_name}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to fetch similar artists for {artist_name}: {e}")
            return []
    
    def get_artist_top_tracks(self, artist_name: str, limit: int = 20) -> List[Dict]:
        """
        Get top tracks for an artist.
        
        Args:
            artist_name: Name of the artist
            limit: Number of tracks to return (max 1000)
        
        Returns:
            List of track dicts with standardized format:
            {
                'track': str (normalized track name),
                'artist': str (normalized artist name),
                'playcount': int,
                'listeners': int,
                'mbid': str,
                'url': str
            }
        """
        try:
            data = self._make_request('artist.gettoptracks', {
                'artist': artist_name,
                'limit': limit
            })
            
            tracks = data.get('toptracks', {}).get('track', [])
            
            if isinstance(tracks, dict):
                tracks = [tracks]
            
            result = []
            for track in tracks:
                track_name = track.get('name', '')
                if track_name:
                    result.append({
                        'track': normalize_text(track_name),
                        'track_display': track_name,
                        'artist': normalize_text(artist_name),
                        'artist_display': artist_name,
                        'playcount': int(track.get('playcount', 0)),
                        'listeners': int(track.get('listeners', 0)),
                        'mbid': track.get('mbid', ''),
                        'url': track.get('url', '')
                    })
            
            logger.debug(f"Fetched {len(result)} top tracks for {artist_name}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to fetch top tracks for {artist_name}: {e}")
            return []
    
    def get_track_info(self, artist_name: str, track_name: str) -> Optional[Dict]:
        """
        Get detailed information about a specific track.
        
        Args:
            artist_name: Name of the artist
            track_name: Name of the track
        
        Returns:
            Track info dict or None if not found
        """
        try:
            data = self._make_request('track.getInfo', {
                'artist': artist_name,
                'track': track_name
            })
            
            track = data.get('track', {})
            if not track:
                return None
            
            tags = []
            tag_data = track.get('toptags', {}).get('tag', [])
            if isinstance(tag_data, dict):
                tag_data = [tag_data]
            tags = [normalize_text(t.get('name', '')) for t in tag_data if t.get('name')]
            
            artist_info = track.get('artist', {})
            if isinstance(artist_info, dict):
                artist_resolved = artist_info.get('name', artist_name)
            else:
                artist_resolved = artist_info or artist_name
            
            return {
                'track': normalize_text(track.get('name', track_name)),
                'track_display': track.get('name', track_name),
                'artist': normalize_text(artist_resolved),
                'artist_display': artist_resolved,
                'album': track.get('album', {}).get('title', ''),
                'playcount': int(track.get('playcount', 0)),
                'listeners': int(track.get('listeners', 0)),
                'duration': int(track.get('duration', 0)),
                'mbid': track.get('mbid', ''),
                'url': track.get('url', ''),
                'tags': tags[:5]
            }
            
        except Exception as e:
            logger.warning(f"Failed to fetch track info for {artist_name} - {track_name}: {e}")
            return None
    
    def get_user_track_playcount(self, artist_name: str, track_name: str) -> int:
        """
        Get the user's playcount for a specific track.
        
        This checks if the authenticated user has ever played this track on Last.fm.
        Returns 0 if the track has never been scrobbled, or > 0 if it has.
        
        Args:
            artist_name: Name of the artist
            track_name: Name of the track
        
        Returns:
            User's playcount for this track (0 if never played)
        """
        if not self.username:
            logger.warning("No username configured - cannot check user playcount")
            return 0
        
        try:
            data = self._make_request('track.getInfo', {
                'artist': artist_name,
                'track': track_name,
                'username': self.username
            })
            
            track = data.get('track', {})
            if not track:
                return 0
            
            # The 'userplaycount' field is only present if username is provided
            user_playcount = int(track.get('userplaycount', 0))
            
            logger.debug(f"User playcount for {artist_name} - {track_name}: {user_playcount}")
            return user_playcount
            
        except Exception as e:
            logger.debug(f"Could not fetch user playcount for {artist_name} - {track_name}: {e}")
            # If we can't determine, assume it's not played (better to include than exclude)
            return 0
    
    def get_artist_tags(self, artist_name: str, limit: int = 10) -> List[str]:
        """
        Get top tags (genres) for an artist.
        
        Args:
            artist_name: Name of the artist
            limit: Number of tags to return
        
        Returns:
            List of normalized tag names
        """
        try:
            data = self._make_request('artist.gettoptags', {
                'artist': artist_name,
                'limit': limit
            })
            
            tags = data.get('toptags', {}).get('tag', [])
            
            if isinstance(tags, dict):
                tags = [tags]
            
            ignore_tags = {'seen live', 'awesome', 'under 2000 listeners', 'favorite', 'favourites'}
            result = []
            
            for tag in tags:
                tag_name = normalize_text(tag.get('name', ''))
                if tag_name and tag_name not in ignore_tags and not any(x in tag_name for x in ['live', 'favorite']):
                    result.append(tag_name)
            
            logger.debug(f"Fetched {len(result)} tags for {artist_name}")
            return result[:limit]
            
        except Exception as e:
            logger.warning(f"Failed to fetch tags for {artist_name}: {e}")
            return []


def get_lastfm_client(api_key: Optional[str] = None, username: Optional[str] = None) -> LastFmClient:
    """
    Factory function to create Last.fm client with credentials from environment.
    
    Args:
        api_key: Last.fm API key (defaults to LASTFM_API_KEY env var)
        username: Last.fm username (defaults to LASTFM_USERNAME env var)
    
    Returns:
        Configured LastFmClient instance
    
    Raises:
        ValueError: If API key is not provided
    """
    api_key = api_key or os.getenv('LASTFM_API_KEY')
    username = username or os.getenv('LASTFM_USERNAME')
    
    if not api_key:
        raise ValueError(
            "Last.fm API key is required. Set LASTFM_API_KEY environment variable "
            "or pass api_key parameter."
        )
    
    return LastFmClient(api_key=api_key, username=username)
