import logging
import uuid
from datetime import datetime

from spotify_client import get_spotify
from database import init_db, store_recent_tracks, get_played_tracks, log_run_stats, get_stats
from discovery import generate_discovery_tracks, ensure_playlist, update_playlist

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Phase 9: Complete unplayed pipeline.
    
    Pipeline:
    1. Authenticate with Spotify
    2. Fetch recently played tracks
    3. Store them in SQLite
    4. Generate candidate tracks
    5. Remove already-played tracks
    6. Remove duplicates (via discovery logic)
    7. Shuffle tracks
    8. Update playlist
    9. Log statistics
    """
    
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting Discovery Engine pipeline (run_id: {run_id})")
    
    try:
        # Phase 1: Authenticate
        logger.info("Step 1: Authenticating with Spotify...")
        sp = get_spotify()
        logger.info("✓ Authentication successful")
        
        # Phase 2: Initialize database
        logger.info("Step 2: Initializing database...")
        init_db()
        logger.info("✓ Database initialized")
        
        # Phase 3: Fetch and store recently played tracks
        logger.info("Step 3: Fetching recently played tracks...")
        store_recent_tracks(sp)
        logger.info("✓ Recently played tracks stored")
        
        # Phase 4: Load played tracks for filtering
        logger.info("Step 4: Loading play history for filtering...")
        played_tracks = get_played_tracks()
        logger.info(f"✓ Loaded {len(played_tracks)} played tracks")
        
        # Phase 5: Generate candidate tracks with filtering
        logger.info("Step 5: Generating intelligent discovery tracks...")
        tracks, filtered_count, api_stats = generate_discovery_tracks(sp, target=40, exclude_played=played_tracks)
        logger.info(f"✓ Generated {len(tracks)} unplayed discovery tracks")
        
        # Phase 6: Update playlist with deduplication
        logger.info("Step 6: Ensuring playlist exists...")
        playlist_id = ensure_playlist(sp)
        logger.info(f"✓ Playlist ready: {playlist_id}")
        
        logger.info("Step 7: Updating playlist with new tracks...")
        added_count = update_playlist(sp, playlist_id, tracks)
        logger.info(f"✓ Added {added_count} new tracks to playlist")
        
        # Phase 7: Log statistics
        logger.info("Step 8: Logging statistics...")
        log_run_stats(run_id, added_count, filtered_count, api_stats)
        stats = get_stats()
        logger.info(f"✓ Statistics logged")
        logger.info(
            f"Total tracks played: {stats['total_tracks_played']}, "
            f"Unique artists: {stats['unique_artists']}, "
            f"Discovery rate: {stats['discovery_rate']}"
        )
        
        logger.info("=" * 60)
        logger.info("DISCOVERY ENGINE COMPLETE")
        logger.info(f"Playlist ID: {playlist_id}")
        logger.info(f"Tracks added: {added_count}")
        logger.info(f"Tracks filtered: {filtered_count}")
        logger.info("=" * 60)
        
        return {
            "success": True,
            "run_id": run_id,
            "playlist_id": playlist_id,
            "tracks_added": added_count,
            "tracks_filtered": filtered_count,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return {
            "success": False,
            "run_id": run_id,
            "error": str(e)
        }


if __name__ == "__main__":
    result = main()
    if not result["success"]:
        exit(1)
