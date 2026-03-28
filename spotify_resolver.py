"""
Spotify URI Resolver for the Unplayed music discovery system.

This module is the FINAL stage of the pipeline - it translates
canonical track IDs (from Last.fm + exports) into Spotify URIs
for playlist management.

Key principle: Spotify API is used ONLY for search/resolution,
NOT for user history or recommendations.
"""

import logging
from typing import Optional, Dict
from difflib import SequenceMatcher
from utils import normalize_text

logger = logging.getLogger(__name__)


class SpotifyResolver:
    """
    Resolves artist + track names to Spotify URIs via search API.
    
    Features:
    - Spotify search with fuzzy matching validation
    - Request caching to avoid redundant searches
    - Graceful 403 handling for free-tier users
    """
    
    def __init__(self, sp_client):
        """
        Initialize resolver with Spotify client.
        
        Args:
            sp_client: Authenticated spotipy.Spotify instance
        """
        self.sp = sp_client
        self.cache: Dict[str, Optional[str]] = {}
        self.stats = {
            'cache_hits': 0,
            'api_calls': 0,
            'successful_resolutions': 0,
            'failed_resolutions': 0,
            'fuzzy_match_failures': 0
        }
    
    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.85) -> bool:
        """
        Check if two strings match using fuzzy string comparison.
        
        Args:
            text1: First string (normalized)
            text2: Second string (normalized)
            threshold: Minimum similarity ratio (0.0-1.0)
        
        Returns:
            True if strings are similar enough, False otherwise
        """
        if not text1 or not text2:
            return False
        
        ratio = SequenceMatcher(None, text1, text2).ratio()
        return ratio >= threshold
    
    def resolve_track_to_uri(
        self,
        artist: str,
        track: str,
        market: str = "US"
    ) -> Optional[str]:
        """
        Resolve a track to its Spotify URI using search API.
        
        Process:
        1. Check cache for previous resolution
        2. Search Spotify with "track:{track} artist:{artist}" query
        3. Validate top result with fuzzy matching
        4. Cache and return URI or None
        
        Args:
            artist: Artist name (will be normalized for matching)
            track: Track name (will be normalized for matching)
            market: ISO country code for market-specific results
        
        Returns:
            Spotify URI (e.g., "spotify:track:1234...") or None if not found
        """
        # Generate cache key from normalized inputs
        normalized_artist = normalize_text(artist)
        normalized_track = normalize_text(track)
        cache_key = f"{normalized_artist}|{normalized_track}"
        
        # Check cache
        if cache_key in self.cache:
            self.stats['cache_hits'] += 1
            logger.debug(f"Cache hit: {artist} - {track}")
            return self.cache[cache_key]
        
        # Perform Spotify search
        try:
            self.stats['api_calls'] += 1
            
            # Use Spotify's structured search query
            query = f'track:"{track}" artist:"{artist}"'
            logger.debug(f"Searching Spotify: {query}")
            
            results = self.sp.search(
                q=query,
                type='track',
                limit=1,
                market=market
            )
            
            items = results.get('tracks', {}).get('items', [])
            
            if not items:
                logger.debug(f"No results for: {artist} - {track}")
                self.cache[cache_key] = None
                self.stats['failed_resolutions'] += 1
                return None
            
            # Validate top result with fuzzy matching
            top_result = items[0]
            result_track = top_result.get('name', '')
            result_artists = top_result.get('artists', [])
            result_artist = result_artists[0].get('name', '') if result_artists else ''
            
            # Normalize results for comparison
            result_track_norm = normalize_text(result_track)
            result_artist_norm = normalize_text(result_artist)
            
            # Fuzzy match validation
            track_match = self._fuzzy_match(normalized_track, result_track_norm)
            artist_match = self._fuzzy_match(normalized_artist, result_artist_norm)
            
            if not track_match or not artist_match:
                logger.warning(
                    f"Fuzzy match failed for '{artist} - {track}' "
                    f"(found: '{result_artist} - {result_track}')"
                )
                self.stats['fuzzy_match_failures'] += 1
                self.cache[cache_key] = None
                self.stats['failed_resolutions'] += 1
                return None
            
            # Extract URI
            uri = top_result.get('uri')
            if not uri:
                logger.warning(f"No URI in result for: {artist} - {track}")
                self.cache[cache_key] = None
                self.stats['failed_resolutions'] += 1
                return None
            
            logger.debug(f"✓ Resolved: {artist} - {track} -> {uri}")
            self.cache[cache_key] = uri
            self.stats['successful_resolutions'] += 1
            return uri
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle 403 Forbidden gracefully (common for free users)
            if '403' in error_msg or 'Forbidden' in error_msg:
                logger.warning(
                    f"Spotify API 403 Forbidden for '{artist} - {track}' "
                    "(possible rate limit or free-tier restriction)"
                )
            else:
                logger.error(f"Error resolving '{artist} - {track}': {e}")
            
            self.cache[cache_key] = None
            self.stats['failed_resolutions'] += 1
            return None
    
    def resolve_batch(
        self,
        tracks: list[Dict[str, str]],
        max_failures: int = 10
    ) -> list[str]:
        """
        Resolve multiple tracks to URIs with early stopping on repeated failures.
        
        Args:
            tracks: List of dicts with 'artist' and 'track' keys
            max_failures: Stop after this many consecutive failures (rate limit protection)
        
        Returns:
            List of Spotify URIs (excludes failed resolutions)
        """
        uris = []
        consecutive_failures = 0
        
        for track_info in tracks:
            artist = track_info.get('artist', '')
            track = track_info.get('track', '')
            
            if not artist or not track:
                logger.warning(f"Skipping track with missing data: {track_info}")
                continue
            
            uri = self.resolve_track_to_uri(artist, track)
            
            if uri:
                uris.append(uri)
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
                # Early stopping if hitting too many failures in a row
                if consecutive_failures >= max_failures:
                    logger.warning(
                        f"Stopping batch resolution after {max_failures} "
                        f"consecutive failures (possible rate limit)"
                    )
                    break
        
        logger.info(
            f"Batch resolution: {len(uris)}/{len(tracks)} successful "
            f"({self.stats['cache_hits']} cache hits, "
            f"{self.stats['api_calls']} API calls)"
        )
        
        return uris
    
    def get_statistics(self) -> Dict:
        """
        Get resolver statistics.
        
        Returns:
            Dict with performance metrics
        """
        return {
            **self.stats,
            'cache_size': len(self.cache),
            'cache_hit_rate': (
                self.stats['cache_hits'] / 
                max(1, self.stats['cache_hits'] + self.stats['api_calls'])
            )
        }
    
    def clear_cache(self):
        """Clear the resolution cache."""
        self.cache.clear()
        logger.info("Resolver cache cleared")


def create_resolver(sp_client) -> SpotifyResolver:
    """
    Factory function to create a SpotifyResolver instance.
    
    Args:
        sp_client: Authenticated spotipy.Spotify instance
    
    Returns:
        Configured SpotifyResolver
    """
    return SpotifyResolver(sp_client)
