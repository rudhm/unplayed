import random
import logging
import time
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries=3, base_delay=1):
    """
    Decorator for retrying Spotify API calls with exponential backoff.
    Handles rate limits (HTTP 429) by reading Retry-After header.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds between retries
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


@retry_with_backoff(max_retries=3, base_delay=1)
def get_related_artists_tracks(sp, artist_id, market="IN"):
    """
    Fetch top tracks from artists related to a seed artist.
    
    Args:
        sp: Spotipy client instance
        artist_id: Seed artist ID
        market: Market code (default "IN" for India)
    
    Returns:
        list: Track IDs from related artists
    """
    track_ids = []
    try:
        # Fetch related artists for the seed artist
        related = sp.artist_related_artists(artist_id)
        related_artists = related.get('artists', [])
        
        if not related_artists:
            return track_ids
        
        # Pick 1-2 random related artists
        sample_size = min(2, len(related_artists))
        sampled_artists = random.sample(related_artists, sample_size)
        
        # Get top tracks for each sampled related artist
        for rel_artist in sampled_artists:
            try:
                top_tracks = sp.artist_top_tracks(rel_artist['id'], market=market)
                for track in top_tracks.get('tracks', [])[:5]:  # Take up to 5 per artist
                    if track.get('id'):
                        track_ids.append(track['id'])
            except Exception as e:
                logger.warning(f"Error fetching tracks for related artist {rel_artist.get('id')}: {e}")
        
        return track_ids
    except Exception as e:
        logger.warning(f"Error fetching related artists for {artist_id}: {e}")
        return track_ids


@retry_with_backoff(max_retries=3, base_delay=1)
def get_search_api_tracks(sp, genre, market="IN", limit=10):
    """
    Fetch tracks using Spotify Search API filtered by genre.
    
    Args:
        sp: Spotipy client instance
        genre: Genre to search for
        market: Market code (default "IN" for India)
        limit: Number of tracks to return (max 10)
    
    Returns:
        list: Track IDs from search results
    """
    track_ids = []
    try:
        results = sp.search(q=f'genre:"{genre}"', type="track", limit=limit, market=market)
        for track in results.get('tracks', {}).get('items', []):
            if track.get('id'):
                track_ids.append(track['id'])
        return track_ids
    except Exception as e:
        logger.warning(f"Error searching for genre '{genre}': {e}")
        return track_ids


@retry_with_backoff(max_retries=3, base_delay=1)
def get_seed_artists_with_fallbacks(sp):
    """
    Get seed artists with a graceful fallback hierarchy for cold-start users.
    
    Fallback order:
    1. Primary: User's top artists (current_user_top_artists)
    2. Fallback 1: User's recently played tracks (extract artist IDs)
    3. Fallback 2 (Cold Start): Empty list (skip taste portion entirely)
    
    Returns:
        tuple: (list of artist IDs, genres set, is_cold_start boolean)
    """
    try:
        # Primary: Try top artists
        top_artists_response = sp.current_user_top_artists(limit=20, time_range='short_term')
        top_artists = top_artists_response.get('items', [])
        
        if top_artists:
            taste_genres = set()
            for artist in top_artists:
                taste_genres.update(artist.get('genres', []))
            
            artist_ids = [a['id'] for a in random.sample(top_artists, min(5, len(top_artists)))]
            logger.info(f"Using {len(artist_ids)} seed artists from top artists")
            return artist_ids, taste_genres, False
        
        logger.info("No top artists found, trying recently played tracks...")
        
        # Fallback 1: Try recently played
        recently_played = sp.current_user_recently_played(limit=20)
        recent_artists = set()
        for item in recently_played.get('items', []):
            track = item.get('track', {})
            for artist in track.get('artists', []):
                recent_artists.add(artist['id'])
        
        if recent_artists:
            # Extract genres from recent artists
            taste_genres = set()
            for artist_id in list(recent_artists)[:5]:
                try:
                    artist = sp.artist(artist_id)
                    taste_genres.update(artist.get('genres', []))
                except Exception as e:
                    logger.warning(f"Error fetching artist {artist_id}: {e}")
            
            artist_ids = list(random.sample(recent_artists, min(5, len(recent_artists))))
            logger.info(f"Using {len(artist_ids)} seed artists from recently played")
            return artist_ids, taste_genres, False
        
        logger.warning("No listening history found - cold start user detected")
        return [], set(), True
        
    except Exception as e:
        logger.error(f"Error getting seed artists: {e}")
        return [], set(), False


def generate_discovery_tracks(sp, target=40, exclude_played=None):
    """
    Generate intelligent discovery candidate tracks based on user taste.
    
    NEW Strategy (Recommendations API Fallback):
    1. Get seed artists with fallback hierarchy:
       - Primary: User's top artists
       - Fallback 1: Recently played tracks (extract artists)
       - Fallback 2 (Cold Start): None (skip taste portion)
    
    2. Taste Portion (80% if seed artists available):
       - For each seed artist, fetch related artists
       - Pick top tracks from related artists
       - Add to candidate pool
    
    3. Wildcard Portion (20% normally, 100% for cold start):
       - Pick random genres NOT in user's taste
       - Use Search API with genre filter: sp.search(q=f'genre:"{genre}"')
       - Add to candidate pool
    
    4. Filtering:
       - Filter out all tracks in exclude_played set
       - Loop until target count is reached
    
    Args:
        sp: Spotipy client instance
        target: Number of unplayed tracks to return (default 40)
        exclude_played: Set of track IDs to exclude (already played tracks)
    
    Returns:
        tuple: (list of track IDs, count of filtered tracks)
    """
    if exclude_played is None:
        exclude_played = set()
    
    all_tracks = []
    filtered_count = 0
    iterations = 0
    max_iterations = 10
    
    while len(all_tracks) < target and iterations < max_iterations:
        iterations += 1
        logger.info(f"Discovery iteration {iterations}: collecting tracks (have {len(all_tracks)}/{target})")
        
        try:
            # Step 1: Get seed artists with fallback hierarchy
            seed_artist_ids, taste_genres, is_cold_start = get_seed_artists_with_fallbacks(sp)
            logger.info(f"Cold start user: {is_cold_start}, Seed artists: {len(seed_artist_ids)}")
            
            # Step 2: Fetch taste-based tracks (80%) using related artists API
            taste_tracks = []
            if seed_artist_ids:
                logger.info(f"Fetching taste-based tracks (80%) via Related Artists API...")
                
                taste_quota = min(32, int(target * 0.8))
                for artist_id in seed_artist_ids:
                    if len(taste_tracks) >= taste_quota:
                        break
                    try:
                        related_tracks = get_related_artists_tracks(sp, artist_id, market="IN")
                        taste_tracks.extend(related_tracks)
                    except Exception as e:
                        logger.warning(f"Error getting related artists tracks for {artist_id}: {e}")
                
                logger.info(f"Got {len(taste_tracks)} taste-based tracks from related artists")
            else:
                logger.info("No seed artists available, skipping taste-based portion")
            
            time.sleep(0.5)
            
            # Step 3: Fetch wildcard tracks using Search API
            wildcard_tracks = []
            try:
                available_genres = sp.recommendation_genre_seeds()['genres']
                wildcard_genres = [g for g in available_genres if g not in taste_genres]
                
                if wildcard_genres:
                    # For cold start, use 100% wildcard; otherwise 20%
                    wildcard_quota = target if is_cold_start else min(8, int(target * 0.2))
                    
                    while len(wildcard_tracks) < wildcard_quota and wildcard_genres:
                        sampled_wildcard = random.sample(
                            wildcard_genres,
                            min(2, len(wildcard_genres))
                        )
                        logger.info(f"Fetching wildcard tracks ({len(wildcard_tracks)}/{wildcard_quota}) "
                                  f"via Search API with genres: {sampled_wildcard}")
                        
                        for genre in sampled_wildcard:
                            if len(wildcard_tracks) >= wildcard_quota:
                                break
                            try:
                                search_tracks = get_search_api_tracks(sp, genre, market="IN", limit=10)
                                wildcard_tracks.extend(search_tracks)
                            except Exception as e:
                                logger.warning(f"Error searching genre '{genre}': {e}")
                    
                    logger.info(f"Got {len(wildcard_tracks)} wildcard tracks from Search API")
            except Exception as e:
                logger.warning(f"Error fetching wildcard tracks: {e}")
            
            time.sleep(0.5)
            
            # Step 4: Combine and filter
            iteration_tracks = taste_tracks + wildcard_tracks
            initial_count = len(iteration_tracks)
            
            for track_id in iteration_tracks:
                if track_id not in exclude_played and track_id not in all_tracks:
                    all_tracks.append(track_id)
            
            iteration_filtered = initial_count - len([t for t in iteration_tracks if t not in exclude_played])
            filtered_count += iteration_filtered
            
            logger.info(
                f"Iteration {iterations}: {len(iteration_tracks)} tracks fetched, "
                f"{iteration_filtered} filtered (already played), "
                f"{len(all_tracks)} total unique unplayed"
            )
            
        except Exception as e:
            logger.error(f"Error in iteration {iterations}: {e}")
            break
        
        if len(all_tracks) < target:
            time.sleep(1)
    
    # Shuffle for randomness
    random.shuffle(all_tracks)
    
    result_count = min(len(all_tracks), target)
    logger.info(
        f"Generated {result_count} unplayed discovery tracks in {iterations} iterations "
        f"(filtered {filtered_count} already-played tracks)"
    )
    
    return all_tracks[:target], filtered_count


def ensure_playlist(sp, name="Discovery Engine"):
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
