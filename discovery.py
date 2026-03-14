import random
import logging
import time
import os
import requests
from datetime import datetime
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")

# Hardcoded diverse genres for wildcard portion (20% of discovery)
# Used since Spotify removed the recommendation_genre_seeds() endpoint
WILDCARD_GENRES = [
    "jazz", "classical", "metal", "reggae", "electronic",
    "folk", "ambient", "blues", "country", "disco",
    "funk", "grunge", "indie", "punk", "soul", "techno"
]

def score_track(track):
    """
    Mathematical scoring based on popularity (60%) and freshness (40%).
    """
    release_date_str = track.get('release_date')
    if not release_date_str:
        return 0.0
    
    try:
        if len(release_date_str) == 4: # YYYY
            release_date = datetime.strptime(release_date_str, "%Y")
        elif len(release_date_str) == 7: # YYYY-MM
            release_date = datetime.strptime(release_date_str, "%Y-%m")
        else: # YYYY-MM-DD (or longer, but we take first 10 chars)
            release_date = datetime.strptime(release_date_str[:10], "%Y-%m-%d")
    except (ValueError, IndexError):
        return 0.0

    age_in_days = max(0, (datetime.now() - release_date).days)
    freshness_score = 1 / (1 + age_in_days / 365.0)
    popularity_score = track.get('popularity', 0) / 100.0
    
    return (0.6 * popularity_score) + (0.4 * freshness_score)


def retry_with_backoff(max_retries=3, base_delay=1):
    """
    Decorator for retrying API calls with exponential backoff.
    Handles rate limits (HTTP 429) by reading Retry-After header.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check for rate limit (HTTP 429)
                    if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                        retry_after = int(e.response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                        logger.warning(
                            f"Rate limited (429). "
                            f"Attempt {attempt + 1}/{max_retries}. "
                            f"Sleeping for {retry_after}s"
                        )
                        time.sleep(retry_after)
                    else:
                        # For other errors, use exponential backoff
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                f"Error in {func.__name__}: {e}. "
                                f"Attempt {attempt + 1}/{max_retries}. "
                                f"Retrying in {delay}s"
                            )
                            time.sleep(delay)
                        else:
                            logger.error(f"Max retries exceeded for {func.__name__}: {e}")
                            raise
            return None
        return wrapper
    return decorator


def get_lastfm_genres(artist_name):
    """
    Fetch top tags (genres) for an artist from Last.fm API.
    Filters out non-genre tags and returns the top 3-5 tags.
    """
    if not LASTFM_API_KEY:
        logger.warning("LASTFM_API_KEY not found in environment")
        return []

    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist={artist_name}&api_key={LASTFM_API_KEY}&format=json"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        tags = data.get('toptags', {}).get('tag', [])
        if not tags:
            return []
            
        # Filter to ignore non-genre tags
        ignore_tags = {'seen live', 'awesome', 'under 2000 listeners', 'favorite', 'favourites'}
        filtered_genres = []
        
        for t in tags:
            tag_name = t.get('name', '').lower()
            if tag_name and tag_name not in ignore_tags and not any(x in tag_name for x in ['live', 'favorite']):
                filtered_genres.append(tag_name)
            
            if len(filtered_genres) >= 5:
                break
                
        return filtered_genres[:5] if len(filtered_genres) >= 3 else filtered_genres
    except Exception as e:
        logger.warning(f"Error fetching Last.fm genres for '{artist_name}': {e}")
        return []


@retry_with_backoff(max_retries=3, base_delay=1)
def get_search_api_tracks(sp, genre, market="IN", limit=10):
    """
    Fetch tracks using Spotify Search API filtered by genre.
    Uses random offset to ensure variety across multiple calls.
    Returns list of track metadata dicts.
    """
    tracks_metadata = []
    try:
        offset = random.randint(0, 500)
        results = sp.search(q=f'genre:"{genre}"', type="track", limit=limit, offset=offset, market=market)
        for track in results.get('tracks', {}).get('items', []):
            if track.get('id') and track.get('artists'):
                tracks_metadata.append({
                    'id': track['id'],
                    'artist_id': track['artists'][0]['id'],
                    'popularity': track.get('popularity', 0),
                    'release_date': track.get('album', {}).get('release_date', '')
                })
        return tracks_metadata
    except Exception as e:
        logger.warning(f"Error searching for genre '{genre}': {e}")
        return tracks_metadata


@retry_with_backoff(max_retries=3, base_delay=1)
def build_taste_profile_genres(sp):
    """
    Aggregate unique genres using Last.fm API as a workaround for Spotify's
    deprecated genre data and locked-down artist lookups.
    """
    taste_genres = set()
    artist_names = set()
    
    # Source 1: Top Artists
    logger.info("Building taste profile: fetching top artists...")
    try:
        top_artists_response = sp.current_user_top_artists(limit=20, time_range='short_term')
        for artist in top_artists_response.get('items', []):
            artist_names.add(artist['name'])
    except Exception as e:
        logger.warning(f"Error fetching top artists: {e}")
    
    # Source 2: Followed Artists
    logger.info("Building taste profile: fetching followed artists...")
    try:
        followed_response = sp.current_user_followed_artists(limit=20)
        for artist in followed_response.get('artists', {}).get('items', []):
            artist_names.add(artist['name'])
    except Exception as e:
        logger.warning(f"Error fetching followed artists: {e}")
    
    # Source 3: Liked Songs (Saved Tracks)
    logger.info("Building taste profile: fetching liked songs...")
    try:
        saved_tracks_response = sp.current_user_saved_tracks(limit=30)
        for item in saved_tracks_response.get('items', []):
            artists = item.get('track', {}).get('artists', [])
            if artists:
                artist_names.add(artists[0]['name'])
    except Exception as e:
        logger.warning(f"Error fetching liked songs: {e}")
    
    # Source 4: Personal Playlists
    logger.info("Building taste profile: fetching personal playlists...")
    try:
        playlists_response = sp.current_user_playlists(limit=10)
        playlists = playlists_response.get('items', [])
        current_user_id = sp.me().get('id')
        
        owned_playlists = [p for p in playlists if p.get('owner', {}).get('id') == current_user_id]
        
        for playlist in owned_playlists[:3]:
            try:
                # Using the new 2026 endpoint /items
                playlist_items_response = sp._get(f"playlists/{playlist['id']}/items", params={"limit": 20})
                for item in playlist_items_response.get('items', []):
                    track = item.get('track')
                    if track and track.get('artists'):
                        artist_names.add(track['artists'][0]['name'])
            except Exception as e:
                logger.warning(f"Error processing playlist '{playlist.get('name')}': {e}")
    except Exception as e:
        logger.warning(f"Error fetching playlists: {e}")

    # Sample artist names and fetch genres from Last.fm
    if artist_names:
        sampled_artists = random.sample(list(artist_names), min(25, len(artist_names)))
        logger.info(f"Fetching genres for {len(sampled_artists)} artists from Last.fm...")
        
        for name in sampled_artists:
            genres = get_lastfm_genres(name)
            if genres:
                taste_genres.update(genres)
            time.sleep(0.25) # Respect Last.fm rate limits
    
    logger.info(f"Taste profile complete: {len(taste_genres)} unique genres aggregated via Last.fm")
    return taste_genres


def generate_discovery_tracks(sp, target=40, exclude_played=None):
    """
    Generate discovery tracks using V2 Architecture:
    1. Candidate Pooling: Gather >= 120 unique unplayed tracks.
    2. Mathematical Scoring: Score tracks by popularity and freshness.
    3. Diversity Constraints: Limit to 2 tracks per artist.
    
    Args:
        sp: Spotipy client instance
        target: Number of unplayed tracks to return (default 40)
        exclude_played: Set of track IDs to exclude (already played tracks)
    
    Returns:
        tuple: (list of track IDs, count of filtered tracks)
    """
    if exclude_played is None:
        exclude_played = set()
    
    candidate_pool = []
    seen_ids = set()
    filtered_count = 0
    iterations = 0
    max_iterations = 15
    pool_size_goal = 120
    
    # Build comprehensive taste profile at the start
    logger.info("Building comprehensive taste profile...")
    taste_genres = build_taste_profile_genres(sp)
    is_cold_start = len(taste_genres) == 0
    logger.info(f"Taste profile: {len(taste_genres)} unique genres, Cold start: {is_cold_start}")
    
    while len(candidate_pool) < pool_size_goal and iterations < max_iterations:
        iterations += 1
        logger.info(f"Discovery iteration {iterations}: collecting candidates (have {len(candidate_pool)}/{pool_size_goal})")
        
        try:
            # Step 1: Fetch taste-based tracks (80%) using Search API
            taste_tracks = []
            if taste_genres:
                taste_quota = min(40, int(pool_size_goal * 0.8))
                genres_to_search = random.sample(list(taste_genres), min(10, len(taste_genres)))
                
                for genre in genres_to_search:
                    if len(taste_tracks) >= taste_quota:
                        break
                    search_results = get_search_api_tracks(sp, genre, market="IN", limit=10)
                    taste_tracks.extend(search_results)
            
            # Step 2: Fetch wildcard tracks (20%)
            wildcard_tracks = []
            available_wildcard = [g for g in WILDCARD_GENRES if g not in taste_genres]
            if available_wildcard:
                wildcard_quota = pool_size_goal if is_cold_start else min(20, int(pool_size_goal * 0.2))
                sampled_wildcard = random.sample(available_wildcard, min(5, len(available_wildcard)))
                
                for genre in sampled_wildcard:
                    if len(wildcard_tracks) >= wildcard_quota:
                        break
                    search_results = get_search_api_tracks(sp, genre, market="IN", limit=10)
                    wildcard_tracks.extend(search_results)
            
            # Step 3: Deduplicate and add to pool
            iteration_tracks = taste_tracks + wildcard_tracks
            initial_count = len(iteration_tracks)
            
            for track in iteration_tracks:
                if track['id'] not in exclude_played and track['id'] not in seen_ids:
                    candidate_pool.append(track)
                    seen_ids.add(track['id'])
            
            iteration_filtered = initial_count - len([t for t in iteration_tracks if t['id'] not in exclude_played])
            filtered_count += iteration_filtered
            
            logger.info(
                f"Iteration {iterations}: {len(iteration_tracks)} tracks fetched, "
                f"{iteration_filtered} filtered (already played), "
                f"{len(candidate_pool)} total unique candidates"
            )
            
        except Exception as e:
            logger.error(f"Error in iteration {iterations}: {e}")
            break
        
        if len(candidate_pool) < pool_size_goal:
            time.sleep(1)
    
    # Step 4: Mathematical Scoring
    logger.info(f"Scoring {len(candidate_pool)} candidates...")
    for track in candidate_pool:
        track['score'] = score_track(track)
    
    # Sort descending by score
    candidate_pool.sort(key=lambda x: x['score'], reverse=True)
    
    # Step 5: Apply Diversity Constraints (Max 2 tracks per artist)
    artist_counts = {}
    final_tracks = []
    
    for track in candidate_pool:
        current_artist_count = artist_counts.get(track['artist_id'], 0)
        if current_artist_count >= 2:
            continue
            
        final_tracks.append(track['id'])
        artist_counts[track['artist_id']] = current_artist_count + 1
        
        if len(final_tracks) >= target:
            break
            
    logger.info(
        f"Final selection: {len(final_tracks)} tracks from {len(artist_counts)} artists. "
        f"(Pool size: {len(candidate_pool)}, Total filtered: {filtered_count})"
    )
    
    return final_tracks, filtered_count

def ensure_playlist(sp, name="Unplayed"):
    """
    Get or create the Discovery Engine playlist.
    
    Args:
        sp: Spotipy client instance
        name: Name of the playlist
    
    Returns:
        str: Spotify playlist ID
    """
    try:
        playlists = sp.current_user_playlists(limit=50)

        for p in playlists["items"]:
            if p["name"] == name:
                logger.info(f"Found existing playlist: {name} ({p['id']})")
                return p["id"]

        playlist = sp._post("me/playlists", payload={"name": name, "public": False})
        
        logger.info(f"Created new playlist: {name} ({playlist['id']})")
        return playlist["id"]
    except Exception as e:
        logger.error(f"Error ensuring playlist: {e}")
        raise


@retry_with_backoff(max_retries=3, base_delay=1)
def get_playlist_tracks(sp, playlist_id):
    """
    Get all track IDs currently in a playlist.
    
    Args:
        sp: Spotipy client instance
        playlist_id: Spotify playlist ID
    
    Returns:
        set: Set of track IDs in the playlist
    """
    existing = set()
    
    try:
        results = sp._get(f"playlists/{playlist_id}/items", params={"limit": 100})
        for item in results["items"]:
            if item.get("track") and item["track"].get("id"):
                existing.add(item["track"]["id"])
        
        # Handle pagination using the next URL
        while results.get("next"):
            results = sp._get(results["next"])
            for item in results["items"]:
                if item.get("track") and item["track"].get("id"):
                    existing.add(item["track"]["id"])
    except Exception as e:
        logger.warning(f"Could not fetch existing playlist tracks: {e}")
    
    return existing


@retry_with_backoff(max_retries=3, base_delay=1)
def update_playlist(sp, playlist_id, tracks):
    """
    Phase 6: Intelligently update playlist with deduplication.
    
    - Fetches current playlist tracks
    - Filters out any tracks already in the playlist
    - Adds new tracks (up to 100 limit)
    - Handles partial updates gracefully
    
    Args:
        sp: Spotipy client instance
        playlist_id: Spotify playlist ID
        tracks: List of track IDs to add
    """
    try:
        # Phase 6: Check what's already in the playlist
        existing_tracks = get_playlist_tracks(sp, playlist_id)
        logger.info(f"Playlist currently has {len(existing_tracks)} tracks")
        
        # Filter out duplicates
        new_tracks = [t for t in tracks if t not in existing_tracks]
        new_count = len(new_tracks)
        
        if new_count == 0:
            logger.info("No new tracks to add - all tracks already in playlist")
            return new_count
        
        logger.info(f"Adding {new_count} new tracks to playlist (filtered {len(tracks) - new_count} duplicates)")
        
        # Replace playlist with deduped tracks (up to 100)
        sp._put(f"playlists/{playlist_id}/items", payload={"uris": [f"spotify:track:{t}" for t in new_tracks[:100]]})
        
        logger.info(f"Added {min(new_count, 100)} new tracks to playlist")
        return min(new_count, 100)
        
    except Exception as e:
        logger.error(f"Error updating playlist: {e}")
        # Don't raise - let the pipeline continue with graceful degradation
        return 0
