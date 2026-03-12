import random
import logging
import time
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    with open("/usr/share/dict/words") as f:
        WORDS = [w.strip().lower() for w in f if len(w.strip()) > 2]
except FileNotFoundError:
    WORDS = [
        "acoustic", "adventure", "ambient", "anthem", "artsy", "atmospheric",
        "ballad", "beats", "beautiful", "bedroom", "big", "bright", "britpop",
        "broken", "chill", "chillhop", "chillwave", "classical", "clean",
        "cloud", "comedy", "country", "covers", "dark", "dance", "deep",
        "demo", "digital", "disco", "diverse", "downtempo", "dreamy", "driving",
        "drone", "dub", "dynamic", "early", "eclectic", "edgy", "electro",
        "electronic", "elegant", "emotional", "energetic", "epic", "ethereal",
        "ethnic", "experimental", "exploration", "expressive", "extreme", "famous",
        "feel", "feeling", "feels", "festival", "film", "final", "flows", "folk",
        "foreign", "forest", "forward", "freak", "fresh", "front", "full",
        "function", "funk", "funky", "future", "futuristic", "garage", "genre",
        "getting", "ghost", "giant", "global", "glitch", "glow", "golden",
        "gospel", "gothic", "great", "groove", "grunge", "group", "growing",
        "guitar", "guitar", "guy", "happy", "hard", "harsh", "head", "heart",
        "heat", "heavy", "hidden", "high", "highlights", "hip", "historic",
        "honest", "horns", "horror", "house", "huge", "human", "humble", "hymns",
        "hypnotic", "iconic", "ideal", "identity", "idyllic", "impact", "indie",
        "indifferent", "industrial", "infinite", "influential", "info", "inspired",
        "instrumental", "intelligent", "intense", "interactive", "interesting",
        "intimate", "intricate", "introspective", "inventive", "iris", "ironic",
        "island", "jazzy", "joyful", "judge", "jungle", "junk", "just", "kanaka",
        "karaoke", "kazoo", "keen", "keep", "kept", "key", "keyboard", "kick",
        "killer", "kind", "kingdom", "knowing", "known", "labor", "landscape",
        "language", "late", "latin", "layers", "layout", "lazy", "leader",
        "leading", "league", "lean", "leap", "learn", "legacy", "legend",
        "leisure", "length", "letter", "level", "liberty", "library", "license",
        "life", "light", "like", "lilt", "limbo", "limit", "line", "linger",
        "lion", "liquid", "listen", "lit", "live", "living", "load", "local",
        "locate", "lock", "locking", "lodge", "loft", "logic", "logical", "lonely",
        "long", "loop", "lose", "loud", "lounge", "love", "lovely", "low", "loyal",
        "lunar", "lunch", "lush", "luxury", "machine", "mad", "made", "magic",
        "magnificent", "major", "make", "making", "male", "mall", "manage",
        "mandatory", "manic", "manifest", "manner", "mansion", "manual", "many",
        "march", "marine", "mark", "market", "marriage", "mass", "massive",
        "master", "match", "mate", "material", "math", "matter", "maximum",
        "maze", "meant", "measure", "meat", "mechanical", "media", "medieval",
        "medium", "meeting", "mellow", "melody", "member", "memo", "memory",
        "mental", "mention", "menu", "mercy", "merge", "merit", "merry", "mesh",
        "message", "metal", "metaphor", "meteor", "method", "metric", "metropolitan"
    ]


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


def random_query():
    return random.choice(WORDS)


@retry_with_backoff(max_retries=3, base_delay=1)
def search_spotify(sp, query, offset):
    """
    Execute a Spotify search with retry logic.
    
    Args:
        sp: Spotipy client instance
        query: Search query string
        offset: Search result offset
    
    Returns:
        dict: Spotify search results
    """
    return sp.search(
        q=query,
        type="track",
        limit=20,
        offset=offset,
        market="IN"
    )


def random_tracks(sp, target=100, num_searches=2, exclude_played=None):
    """
    Generate random candidate tracks using fixed searches.
    
    Strategy: Run a fixed number of searches, collect candidates, deduplicate,
    filter out already-played tracks, shuffle, and sample. This is efficient and predictable.
    
    Example: 2 searches × 20 results = 40 candidates → deduplicate → 
             filter played → shuffle → sample
    
    Args:
        sp: Spotipy client instance
        target: Number of tracks to return (default 100)
        num_searches: Number of search queries to run (default 2)
        exclude_played: Set of track IDs to exclude (already played tracks)
    
    Returns:
        list: Up to `target` unique unplayed track IDs, shuffled
    """
    if exclude_played is None:
        exclude_played = set()
    
    tracks = []
    
    for _ in range(num_searches):
        q = random_query()
        offset = random.randint(0, 900)
        
        try:
            logger.info(f"Search: query='{q}' offset={offset}")
            
            results = search_spotify(sp, q, offset)
            
            for t in results["tracks"]["items"]:
                if t["id"]:
                    tracks.append(t["id"])
                    
        except Exception as e:
            logger.warning(f"Search error for '{q}': {e}")
            continue
        
        # Add small delay between searches to prevent burst limits
        time.sleep(0.5)
    
    # Deduplicate while preserving order
    tracks = list(dict.fromkeys(tracks))
    
    # Phase 5: Filter out already-played tracks
    initial_count = len(tracks)
    tracks = [t for t in tracks if t not in exclude_played]
    filtered_count = initial_count - len(tracks)
    
    logger.info(f"Filtered {filtered_count} played tracks, {len(tracks)} new tracks remaining")
    
    # Shuffle for randomness
    random.shuffle(tracks)
    
    logger.info(f"Generated {len(tracks[:target])} tracks from {initial_count} candidates")
    return tracks[:target], filtered_count


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
        user = sp.me()["id"]

        playlists = sp.current_user_playlists(limit=50)

        for p in playlists["items"]:
            if p["name"] == name:
                logger.info(f"Found existing playlist: {name} ({p['id']})")
                return p["id"]

        playlist = sp.user_playlist_create(
            user,
            name,
            public=False
        )
        
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
        results = sp.playlist_tracks(playlist_id, limit=100)
        for item in results["items"]:
            if item["track"] and item["track"]["id"]:
                existing.add(item["track"]["id"])
        
        # Handle pagination
        while results.get("next"):
            results = sp.next(results)
            for item in results["items"]:
                if item["track"] and item["track"]["id"]:
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
        sp.playlist_replace_items(
            playlist_id,
            new_tracks[:100]
        )
        
        logger.info(f"Added {min(new_count, 100)} new tracks to playlist")
        return min(new_count, 100)
        
    except Exception as e:
        logger.error(f"Error updating playlist: {e}")
        # Don't raise - let the pipeline continue with graceful degradation
        return 0
