import logging
import uuid
import os
from datetime import datetime

from spotify_client import get_spotify
from database import init_db, log_run_stats, get_stats
from discovery import run_full_pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Hybrid Discovery Pipeline.
    
    Architecture:
    1. INTELLIGENCE (Brain): Last.fm API for taste profiles and recommendations
    2. MEMORY (History): Local Spotify GDPR exports for filtering played tracks
    3. OUTPUT (Resolution): Spotify API ONLY for URI resolution and playlist management
    
    Pipeline:
    1. Authenticate with Spotify (output layer only)
    2. Initialize database
    3. Run hybrid discovery pipeline (Last.fm + local exports)
    4. Log statistics
    """
    
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting Hybrid Discovery Engine (run_id: {run_id})")
    
    try:
        # Phase 1: Authenticate with Spotify (OUTPUT LAYER ONLY)
        logger.info("Step 1: Authenticating with Spotify (output layer)...")
        sp = get_spotify()
        logger.info("✓ Spotify authentication successful")
        
        # Phase 2: Initialize database
        logger.info("Step 2: Initializing database...")
        init_db()
        logger.info("✓ Database initialized")
        
        # Phase 3: Run the complete hybrid pipeline
        # This uses Last.fm for intelligence, local exports for filtering,
        # and Spotify ONLY for URI resolution and playlist updates
        logger.info("Step 3: Running hybrid discovery pipeline...")
        logger.info("  → Intelligence layer: Last.fm API")
        logger.info("  → Memory layer: Local Spotify GDPR exports (optional)")
        logger.info("  → Output layer: Spotify API (search & playlists only)")
        
        pipeline_result = run_full_pipeline(
            sp=sp,
            playlist_name="Unplayed Discoveries",
            target=40
        )
        
        if not pipeline_result.get('success', False):
            raise Exception(f"Pipeline failed: {pipeline_result.get('error', 'Unknown error')}")
        
        logger.info("✓ Hybrid discovery pipeline complete")
        
        # Extract results
        playlist_id = pipeline_result.get('playlist_id', '')
        tracks_added = pipeline_result.get('tracks_added', 0)
        stats = pipeline_result.get('stats', {})
        
        # Phase 4: Log run statistics
        logger.info("Step 4: Logging run statistics...")
        
        # Create API stats dict from pipeline results
        api_stats = {
            'top_artists_used': stats.get('top_artists_fetched', 0) > 0,
            'similar_artists_used': stats.get('similar_artists_fetched', 0) > 0,
            'candidates_generated': stats.get('candidates_generated', 0),
            'export_tracks_loaded': stats.get('export_tracks_loaded', 0),
            'api_failures': []
        }
        
        filtered_count = stats.get('tracks_filtered', 0)
        
        log_run_stats(run_id, tracks_added, filtered_count, api_stats)
        db_stats = get_stats()
        logger.info("✓ Statistics logged")
        
        # Final summary
        logger.info("=" * 60)
        logger.info("HYBRID DISCOVERY ENGINE COMPLETE")
        logger.info(f"Playlist ID: {playlist_id}")
        logger.info(f"Tracks added: {tracks_added}")
        logger.info(f"Tracks filtered: {filtered_count}")
        logger.info(f"Intelligence: Last.fm (✓)")
        logger.info(f"Memory: {'GDPR exports (✓)' if stats.get('export_tracks_loaded', 0) > 0 else 'None (skipped)'}")
        logger.info(f"Output: Spotify playlists (✓)")
        logger.info("=" * 60)
        
        return {
            "success": True,
            "run_id": run_id,
            "playlist_id": playlist_id,
            "tracks_added": tracks_added,
            "tracks_filtered": filtered_count,
            "stats": db_stats,
            "pipeline_stats": stats
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
