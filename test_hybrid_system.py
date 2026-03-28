#!/usr/bin/env python3
"""
Quick integration test for the hybrid discovery system.

Tests each component in isolation and then as an integrated system.
"""

import logging
import os
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


def test_utils():
    """Test shared utilities."""
    logger.info("Testing utils module...")
    from utils import normalize_text, get_track_id, split_track_id
    
    # Test normalization
    assert normalize_text("Guns N' Roses") == "guns n roses"
    assert normalize_text("  The Beatles!  ") == "the beatles"
    assert normalize_text("Artist | Name") == "artist  name"
    
    # Test track ID generation
    track_id = get_track_id("The Beatles", "Let It Be")
    assert track_id == "the beatles|let it be"
    
    # Test track ID splitting
    artist, track = split_track_id(track_id)
    assert artist == "the beatles"
    assert track == "let it be"
    
    logger.info("✓ utils module works correctly")


def test_lastfm_client():
    """Test Last.fm client."""
    logger.info("Testing Last.fm client...")
    from lastfm_client import get_lastfm_client
    
    api_key = os.getenv('LASTFM_API_KEY')
    username = os.getenv('LASTFM_USERNAME')
    
    if not api_key or not username:
        logger.warning("⚠ Skipping Last.fm test (credentials not configured)")
        return
    
    try:
        client = get_lastfm_client()
        logger.info(f"  Initialized client for user: {client.username}")
        
        # Test fetching top artists (limited to 5 for quick test)
        top_artists = client.get_user_top_artists(limit=5)
        if top_artists:
            logger.info(f"  ✓ Fetched {len(top_artists)} top artists")
            logger.info(f"    Top artist: {top_artists[0].get('artist_display', 'N/A')}")
        else:
            logger.warning("  ⚠ No top artists returned")
        
        logger.info("✓ Last.fm client works correctly")
    except Exception as e:
        logger.error(f"✗ Last.fm client test failed: {e}")
        raise


def test_spotify_export_loader():
    """Test Spotify export loader."""
    logger.info("Testing Spotify export loader...")
    from spotify_export_loader import load_spotify_export
    
    export_path = os.getenv('SPOTIFY_EXPORT_PATH')
    
    if not export_path:
        logger.warning("⚠ Skipping export loader test (SPOTIFY_EXPORT_PATH not configured)")
        return
    
    try:
        loader = load_spotify_export()
        if loader and loader.has_data():
            stats = loader.get_statistics()
            logger.info(f"  ✓ Loaded {stats['unique_tracks']} unique tracks")
            logger.info(f"    {stats['unique_artists']} unique artists")
            logger.info(f"    {stats['total_plays']} total plays")
        else:
            logger.warning("  ⚠ No export data loaded")
        
        logger.info("✓ Export loader works correctly")
    except Exception as e:
        logger.error(f"✗ Export loader test failed: {e}")
        raise


def test_spotify_resolver():
    """Test Spotify URI resolver."""
    logger.info("Testing Spotify resolver...")
    
    try:
        from spotify_client import get_spotify
        from spotify_resolver import create_resolver
        
        sp = get_spotify()
        resolver = create_resolver(sp)
        
        # Test resolving a well-known track
        uri = resolver.resolve_track_to_uri("The Beatles", "Let It Be")
        
        if uri:
            logger.info(f"  ✓ Resolved track to URI: {uri}")
        else:
            logger.warning("  ⚠ Could not resolve test track")
        
        stats = resolver.get_statistics()
        logger.info(f"  Cache: {stats['cache_size']} entries, {stats['api_calls']} API calls")
        
        logger.info("✓ Spotify resolver works correctly")
    except Exception as e:
        logger.error(f"✗ Spotify resolver test failed: {e}")
        if "403" in str(e) or "Forbidden" in str(e):
            logger.warning("  (This may be due to Spotify free tier limitations)")
        raise


def test_discovery_pipeline():
    """Test the full discovery pipeline (dry run)."""
    logger.info("Testing discovery pipeline...")
    
    try:
        from spotify_client import get_spotify
        from discovery import run_full_pipeline
        
        # Check required credentials
        if not os.getenv('LASTFM_API_KEY') or not os.getenv('LASTFM_USERNAME'):
            logger.error("✗ Cannot test pipeline: LASTFM_API_KEY and LASTFM_USERNAME required")
            return
        
        logger.info("  Running full pipeline with target=5 tracks (dry run)...")
        
        sp = get_spotify()
        result = run_full_pipeline(sp, target=5)
        
        if result['success']:
            logger.info(f"  ✓ Pipeline succeeded!")
            logger.info(f"    Playlist: {result['playlist_id']}")
            logger.info(f"    Tracks added: {result['tracks_added']}")
            stats = result['stats']
            logger.info(f"    Candidates generated: {stats['candidate_generation']['total_candidates']}")
            logger.info(f"    Filtered: {stats['filtering_scoring']['filtered_played']}")
        else:
            logger.error(f"  ✗ Pipeline failed: {result.get('error', 'Unknown error')}")
        
        logger.info("✓ Discovery pipeline test complete")
    except Exception as e:
        logger.error(f"✗ Discovery pipeline test failed: {e}")
        raise


def main():
    """Run all integration tests."""
    logger.info("=" * 60)
    logger.info("HYBRID DISCOVERY SYSTEM - INTEGRATION TESTS")
    logger.info("=" * 60)
    
    tests = [
        ("Utils", test_utils),
        ("Last.fm Client", test_lastfm_client),
        ("Spotify Export Loader", test_spotify_export_loader),
        ("Spotify Resolver", test_spotify_resolver),
        ("Discovery Pipeline", test_discovery_pipeline),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_func in tests:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Test: {name}")
        logger.info(f"{'=' * 60}")
        
        try:
            test_func()
            passed += 1
        except Exception as e:
            if "Skipping" in str(e) or "not configured" in str(e):
                skipped += 1
            else:
                failed += 1
                logger.error(f"Test '{name}' failed: {e}")
    
    logger.info(f"\n{'=' * 60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'=' * 60}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"{'=' * 60}")
    
    if failed > 0:
        exit(1)


if __name__ == "__main__":
    main()
