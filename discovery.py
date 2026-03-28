"""
Hybrid Discovery Engine for Unplayed.

Architecture:
1. INTELLIGENCE (Brain): Last.fm API for taste profiles and candidate generation
2. MEMORY (History): Local Spotify GDPR exports for filtering played tracks
3. OUTPUT (Resolution): Spotify API ONLY for URI resolution and playlist management

This design eliminates the 403 Forbidden errors from Spotify's user data endpoints
by using Last.fm as the primary intelligence layer.
"""

import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
from functools import wraps
import time

from lastfm_client import get_lastfm_client
from spotify_export_loader import load_spotify_export
from spotify_resolver import create_resolver
from utils import get_track_id

logger = logging.getLogger(__name__)


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
                    if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                        retry_after = int(e.response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                        logger.warning(
                            f"Rate limited (429). "
                            f"Attempt {attempt + 1}/{max_retries}. "
                            f"Sleeping for {retry_after}s"
                        )
                        time.sleep(retry_after)
                    else:
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


# =============================================================================
# PHASE 1: TASTE PROFILE (LAST.FM)
# =============================================================================

def build_taste_profile(
    lastfm_client,
    top_artists_limit: int = 50,
    similar_artists_per_seed: int = 10
) -> Tuple[List[Dict], Dict]:
    """
    Build taste profile using Last.fm API.
    
    Strategy:
    1. Fetch user's top artists from Last.fm
    2. For each top artist, fetch similar artists
    3. Combine into expanded artist pool (50-150 artists)
    
    Args:
        lastfm_client: Configured LastFmClient instance
        top_artists_limit: Number of top artists to fetch
        similar_artists_per_seed: Similar artists to fetch per seed
    
    Returns:
        Tuple of (expanded_artists list, stats dict)
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: BUILDING TASTE PROFILE (LAST.FM)")
    logger.info("=" * 60)
    
    stats = {
        'top_artists_fetched': 0,
        'similar_artists_fetched': 0,
        'total_artists_in_pool': 0
    }
    
    # Step 1: Fetch user's top artists
    logger.info(f"Fetching top {top_artists_limit} artists for user...")
    top_artists = lastfm_client.get_user_top_artists(
        period='overall',
        limit=top_artists_limit
    )
    
    if not top_artists:
        logger.error("No top artists found! Cannot build taste profile.")
        return [], stats
    
    stats['top_artists_fetched'] = len(top_artists)
    logger.info(f"✓ Fetched {len(top_artists)} top artists from Last.fm")
    
    # Build artist pool with weights
    artist_pool = {}
    
    # Add top artists with high initial weight
    for idx, artist_data in enumerate(top_artists):
        artist_name = artist_data.get('artist')
        if artist_name:
            # Weight by rank: top artist = 1.0, decreasing linearly
            weight = 1.0 - (idx / len(top_artists)) * 0.5
            artist_pool[artist_name] = {
                'weight': weight,
                'source': 'top_artist',
                'display_name': artist_data.get('artist_display', artist_name)
            }
    
    # Step 2: Expand with similar artists
    logger.info(f"Expanding pool with similar artists...")
    similar_count = 0
    
    # Process top 20 artists for expansion (to limit API calls)
    for seed_artist in top_artists[:20]:
        artist_name = seed_artist.get('artist_display', seed_artist.get('artist'))
        if not artist_name:
            continue
        
        similar = lastfm_client.get_similar_artists(
            artist_name,
            limit=similar_artists_per_seed
        )
        
        for similar_data in similar:
            similar_name = similar_data.get('artist')
            if similar_name and similar_name not in artist_pool:
                # Weight by similarity match score
                match_score = similar_data.get('match', 0.5)
                artist_pool[similar_name] = {
                    'weight': match_score * 0.5,  # Lower weight than top artists
                    'source': 'similar',
                    'display_name': similar_data.get('artist_display', similar_name)
                }
                similar_count += 1
    
    stats['similar_artists_fetched'] = similar_count
    stats['total_artists_in_pool'] = len(artist_pool)
    
    logger.info(f"✓ Taste profile built:")
    logger.info(f"  - {stats['top_artists_fetched']} top artists")
    logger.info(f"  - {stats['similar_artists_fetched']} similar artists")
    logger.info(f"  - {stats['total_artists_in_pool']} total artists in pool")
    
    return artist_pool, stats


# =============================================================================
# PHASE 2: CANDIDATE GENERATION (LAST.FM)
# =============================================================================

def generate_candidates(
    lastfm_client,
    artist_pool: Dict,
    tracks_per_artist: int = 5,
    max_candidates: int = 300
) -> Tuple[List[Dict], Dict]:
    """
    Generate candidate tracks from artist pool using Last.fm.
    
    Strategy:
    1. For each artist in pool, fetch top tracks
    2. Collect metadata: playcount, listeners, artist weight
    3. Return candidate list (200-300 tracks)
    
    Args:
        lastfm_client: Configured LastFmClient instance
        artist_pool: Dict of artist_name -> metadata from build_taste_profile
        tracks_per_artist: Number of tracks to fetch per artist
        max_candidates: Maximum total candidates to generate
    
    Returns:
        Tuple of (candidate_tracks list, stats dict)
    """
    logger.info("=" * 60)
    logger.info("PHASE 2: GENERATING CANDIDATES (LAST.FM)")
    logger.info("=" * 60)
    
    stats = {
        'artists_processed': 0,
        'total_candidates': 0,
        'api_errors': 0
    }
    
    candidates = []
    
    # Sort artists by weight (prioritize top artists)
    sorted_artists = sorted(
        artist_pool.items(),
        key=lambda x: x[1]['weight'],
        reverse=True
    )
    
    logger.info(f"Fetching top tracks for {len(sorted_artists)} artists...")
    
    for artist_name, artist_meta in sorted_artists:
        if len(candidates) >= max_candidates:
            logger.info(f"Reached max candidates ({max_candidates}), stopping")
            break
        
        try:
            display_name = artist_meta.get('display_name', artist_name)
            tracks = lastfm_client.get_artist_top_tracks(
                display_name,
                limit=tracks_per_artist
            )
            
            for track_data in tracks:
                track_id = get_track_id(
                    track_data.get('artist', ''),
                    track_data.get('track', '')
                )
                
                if not track_id:
                    continue
                
                candidates.append({
                    'track_id': track_id,
                    'artist': track_data.get('artist'),
                    'artist_display': track_data.get('artist_display'),
                    'track': track_data.get('track'),
                    'track_display': track_data.get('track_display'),
                    'playcount': track_data.get('playcount', 0),
                    'listeners': track_data.get('listeners', 0),
                    'artist_weight': artist_meta.get('weight', 0.5),
                    'source': artist_meta.get('source', 'unknown')
                })
            
            stats['artists_processed'] += 1
            
            if stats['artists_processed'] % 10 == 0:
                logger.info(f"  Processed {stats['artists_processed']} artists, {len(candidates)} candidates so far")
        
        except Exception as e:
            logger.warning(f"Error fetching tracks for {artist_name}: {e}")
            stats['api_errors'] += 1
    
    stats['total_candidates'] = len(candidates)
    
    logger.info(f"✓ Generated {len(candidates)} candidate tracks")
    logger.info(f"  - {stats['artists_processed']} artists processed")
    logger.info(f"  - {stats['api_errors']} API errors")
    
    return candidates, stats


# =============================================================================
# PHASE 3: FILTERING & SCORING
# =============================================================================

def score_track(
    track_data: Dict,
    export_loader,
    boost_history_artists: bool = True
) -> float:
    """
    Score a candidate track for ranking.
    
    Formula: base_score + history_boost
    - base_score: (0.6 * popularity) + (0.4 * artist_weight)
    - history_boost: +0.2 if artist is in user's play history
    
    Args:
        track_data: Track metadata dict
        export_loader: SpotifyExportLoader instance (optional)
        boost_history_artists: Apply boost for artists in play history
    
    Returns:
        Score between 0.0 and ~1.2
    """
    # Base scoring components
    playcount = track_data.get('playcount', 0)
    listeners = track_data.get('listeners', 0)
    artist_weight = track_data.get('artist_weight', 0.5)
    
    # Popularity score (normalized from playcount/listeners)
    # Use listeners as proxy for popularity (more stable than playcount)
    popularity_score = min(1.0, listeners / 100000.0) if listeners > 0 else 0.0
    
    # Base score: 60% popularity, 40% artist weight
    base_score = (0.6 * popularity_score) + (0.4 * artist_weight)
    
    # History boost: If this artist is in user's Spotify history, boost score
    history_boost = 0.0
    if boost_history_artists and export_loader and export_loader.has_data():
        artist = track_data.get('artist', '')
        artist_freq = export_loader.get_artist_frequency(artist)
        if artist_freq > 0:
            # Boost by up to 0.2 based on how often artist is played
            artist_weight = export_loader.get_artist_weight(artist)
            history_boost = 0.2 * artist_weight
    
    return base_score + history_boost


def filter_and_score_candidates(
    candidates: List[Dict],
    export_loader,
    target_count: int = 40
) -> Tuple[List[Dict], Dict]:
    """
    Filter and score candidates to produce final recommendations.
    
    Process:
    1. Filter out tracks in play history (if export data available)
    2. Score remaining tracks
    3. Sort by score and take top N
    
    Args:
        candidates: List of candidate track dicts
        export_loader: SpotifyExportLoader instance (optional)
        target_count: Number of tracks to return
    
    Returns:
        Tuple of (scored_tracks list, stats dict)
    """
    logger.info("=" * 60)
    logger.info("PHASE 3: FILTERING & SCORING")
    logger.info("=" * 60)
    
    stats = {
        'candidates_input': len(candidates),
        'filtered_played': 0,
        'scored_tracks': 0,
        'final_count': 0
    }
    
    # Filter out played tracks
    unplayed = []
    
    if export_loader and export_loader.has_data():
        logger.info("Filtering out played tracks from export data...")
        for candidate in candidates:
            artist = candidate.get('artist', '')
            track = candidate.get('track', '')
            
            if not export_loader.is_track_played(artist, track):
                unplayed.append(candidate)
            else:
                stats['filtered_played'] += 1
        
        logger.info(f"✓ Filtered {stats['filtered_played']} played tracks")
        logger.info(f"  {len(unplayed)} unplayed candidates remaining")
    else:
        logger.warning("No export data - skipping play history filtering")
        unplayed = candidates
    
    if not unplayed:
        logger.error("No unplayed tracks remaining after filtering!")
        return [], stats
    
    # Score tracks
    logger.info("Scoring candidates...")
    for candidate in unplayed:
        score = score_track(candidate, export_loader)
        candidate['score'] = score
    
    stats['scored_tracks'] = len(unplayed)
    
    # Sort by score and take top N
    sorted_tracks = sorted(unplayed, key=lambda x: x.get('score', 0), reverse=True)
    final_tracks = sorted_tracks[:target_count]
    
    stats['final_count'] = len(final_tracks)
    
    logger.info(f"✓ Scored {len(unplayed)} tracks")
    logger.info(f"  Top score: {final_tracks[0]['score']:.3f}")
    logger.info(f"  Median score: {sorted_tracks[len(sorted_tracks)//2]['score']:.3f}")
    logger.info(f"  Selected top {len(final_tracks)} tracks")
    
    return final_tracks, stats


# =============================================================================
# PHASE 4: SPOTIFY URI RESOLUTION & OUTPUT
# =============================================================================

@retry_with_backoff(max_retries=3, base_delay=1)
def ensure_playlist(sp, playlist_name: str = "Unplayed Discoveries") -> str:
    """
    Ensure discovery playlist exists, create if needed.
    
    Args:
        sp: Spotipy client instance
        playlist_name: Name for the playlist
    
    Returns:
        Playlist ID
    """
    try:
        user_id = sp.me()['id']
        
        # Check for existing playlist
        playlists = sp.current_user_playlists(limit=50)
        for playlist in playlists.get('items', []):
            if playlist.get('name') == playlist_name:
                logger.info(f"✓ Found existing playlist: {playlist_name}")
                return playlist['id']
        
        # Create new playlist
        playlist = sp.user_playlist_create(
            user_id,
            playlist_name,
            public=False,
            description="Personalized music discovery powered by Last.fm + Spotify"
        )
        logger.info(f"✓ Created new playlist: {playlist_name}")
        return playlist['id']
    
    except Exception as e:
        logger.error(f"Error ensuring playlist: {e}")
        raise


@retry_with_backoff(max_retries=3, base_delay=1)
def get_playlist_tracks(sp, playlist_id: str) -> Set[str]:
    """
    Fetch all track URIs currently in a playlist.
    
    Args:
        sp: Spotipy client instance
        playlist_id: Spotify playlist ID
    
    Returns:
        Set of track URIs
    """
    existing = set()
    
    try:
        results = sp.playlist_tracks(playlist_id, limit=100)
        
        while results:
            for item in results.get('items', []):
                track = item.get('track')
                if track and track.get('uri'):
                    existing.add(track['uri'])
            
            if results.get('next'):
                results = sp.next(results)
            else:
                break
    
    except Exception as e:
        logger.warning(f"Could not fetch existing playlist tracks: {e}")
    
    return existing


@retry_with_backoff(max_retries=3, base_delay=1)
def update_playlist(sp, playlist_id: str, track_uris: List[str]) -> int:
    """
    Update playlist with new tracks (deduplication included).
    
    Args:
        sp: Spotipy client instance
        playlist_id: Spotify playlist ID
        track_uris: List of Spotify URIs to add
    
    Returns:
        Number of tracks added
    """
    try:
        # Fetch existing tracks
        existing_uris = get_playlist_tracks(sp, playlist_id)
        logger.info(f"Playlist currently has {len(existing_uris)} tracks")
        
        # Filter out duplicates
        new_uris = [uri for uri in track_uris if uri not in existing_uris]
        
        if not new_uris:
            logger.info("No new tracks to add - all tracks already in playlist")
            return 0
        
        logger.info(f"Adding {len(new_uris)} new tracks (filtered {len(track_uris) - len(new_uris)} duplicates)")
        
        # Spotify API limit: 100 tracks per request
        for i in range(0, len(new_uris), 100):
            batch = new_uris[i:i+100]
            sp.playlist_add_items(playlist_id, batch)
        
        logger.info(f"✓ Added {len(new_uris)} tracks to playlist")
        return len(new_uris)
    
    except Exception as e:
        logger.error(f"Error updating playlist: {e}")
        return 0


def resolve_and_output(
    sp,
    recommendations: List[Dict],
    playlist_name: str = "Unplayed Discoveries"
) -> Tuple[str, int, Dict]:
    """
    Resolve tracks to Spotify URIs and update playlist.
    
    Args:
        sp: Spotipy client instance
        recommendations: List of track dicts with artist/track keys
        playlist_name: Name for the output playlist
    
    Returns:
        Tuple of (playlist_id, tracks_added, stats dict)
    """
    logger.info("=" * 60)
    logger.info("PHASE 4: SPOTIFY URI RESOLUTION & OUTPUT")
    logger.info("=" * 60)
    
    stats = {
        'recommendations_input': len(recommendations),
        'uris_resolved': 0,
        'resolution_failures': 0,
        'tracks_added': 0
    }
    
    # Create resolver
    resolver = create_resolver(sp)
    
    # Resolve tracks to URIs
    logger.info(f"Resolving {len(recommendations)} tracks to Spotify URIs...")
    
    track_list = [
        {
            'artist': rec.get('artist_display', rec.get('artist')),
            'track': rec.get('track_display', rec.get('track'))
        }
        for rec in recommendations
    ]
    
    uris = resolver.resolve_batch(track_list, max_failures=10)
    
    stats['uris_resolved'] = len(uris)
    stats['resolution_failures'] = len(recommendations) - len(uris)
    
    logger.info(f"✓ Resolved {len(uris)}/{len(recommendations)} tracks to URIs")
    
    resolver_stats = resolver.get_statistics()
    logger.info(
        f"  Cache: {resolver_stats['cache_hit_rate']:.1%} hit rate, "
        f"{resolver_stats['api_calls']} API calls"
    )
    
    if not uris:
        logger.error("No URIs resolved! Cannot update playlist.")
        return "", 0, stats
    
    # Ensure playlist exists
    try:
        playlist_id = ensure_playlist(sp, playlist_name)
    except Exception as e:
        logger.error(f"Failed to create/find playlist: {e}")
        return "", 0, stats
    
    # Update playlist
    try:
        tracks_added = update_playlist(sp, playlist_id, uris)
        stats['tracks_added'] = tracks_added
    except Exception as e:
        logger.error(f"Failed to update playlist: {e}")
        return playlist_id, 0, stats
    
    return playlist_id, tracks_added, stats


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def generate_discovery_tracks(
    sp,
    target: int = 40,
    exclude_played: Set[str] = None
) -> Tuple[List[str], int, Dict]:
    """
    Main hybrid discovery pipeline.
    
    Pipeline:
    1. Build taste profile from Last.fm
    2. Generate candidates from Last.fm
    3. Filter & score candidates
    4. Resolve to Spotify URIs
    
    Args:
        sp: Spotipy client instance
        target: Target number of recommendations
        exclude_played: Legacy parameter (now handled by export loader)
    
    Returns:
        Tuple of (track_uris list, filtered_count, stats dict)
    """
    logger.info("\n" + "=" * 60)
    logger.info("HYBRID DISCOVERY ENGINE - STARTING PIPELINE")
    logger.info("=" * 60 + "\n")
    
    pipeline_stats = {
        'taste_profile': {},
        'candidate_generation': {},
        'filtering_scoring': {},
        'resolution_output': {}
    }
    
    # Initialize clients
    try:
        lastfm_client = get_lastfm_client()
    except Exception as e:
        logger.error(f"Failed to initialize Last.fm client: {e}")
        logger.error("Ensure LASTFM_API_KEY and LASTFM_USERNAME are set in environment")
        raise
    
    export_loader = load_spotify_export()
    
    # Phase 1: Build taste profile
    artist_pool, taste_stats = build_taste_profile(lastfm_client)
    pipeline_stats['taste_profile'] = taste_stats
    
    if not artist_pool:
        raise Exception("Failed to build taste profile - no artists found")
    
    # Phase 2: Generate candidates
    candidates, gen_stats = generate_candidates(lastfm_client, artist_pool)
    pipeline_stats['candidate_generation'] = gen_stats
    
    if not candidates:
        raise Exception("Failed to generate candidates - no tracks found")
    
    # Phase 3: Filter and score
    recommendations, filter_stats = filter_and_score_candidates(
        candidates,
        export_loader,
        target_count=target
    )
    pipeline_stats['filtering_scoring'] = filter_stats
    
    if not recommendations:
        raise Exception("No recommendations after filtering")
    
    # Return track data for external playlist management
    # (For compatibility with existing main.py)
    track_ids = [rec.get('track_id', '') for rec in recommendations]
    filtered_count = filter_stats.get('filtered_played', 0)
    
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Taste profile: {taste_stats['total_artists_in_pool']} artists")
    logger.info(f"Candidates: {gen_stats['total_candidates']} tracks")
    logger.info(f"Filtered: {filter_stats['filtered_played']} played tracks")
    logger.info(f"Final: {len(recommendations)} recommendations")
    logger.info("=" * 60 + "\n")
    
    return track_ids, filtered_count, pipeline_stats


def run_full_pipeline(sp, playlist_name: str = "Unplayed Discoveries", target: int = 40):
    """
    Run the complete discovery pipeline with output to Spotify playlist.
    
    This is the new main entry point that replaces the old Spotify-centric approach.
    
    Args:
        sp: Authenticated Spotipy client
        playlist_name: Name for output playlist
        target: Target number of recommendations
    
    Returns:
        Dict with pipeline results
    """
    logger.info("\n" + "=" * 60)
    logger.info("HYBRID DISCOVERY ENGINE - FULL PIPELINE")
    logger.info("=" * 60 + "\n")
    
    all_stats = {}
    
    try:
        # Initialize clients
        lastfm_client = get_lastfm_client()
        export_loader = load_spotify_export()
        
        # Phase 1: Build taste profile
        artist_pool, taste_stats = build_taste_profile(lastfm_client)
        all_stats['taste_profile'] = taste_stats
        
        # Phase 2: Generate candidates
        candidates, gen_stats = generate_candidates(lastfm_client, artist_pool)
        all_stats['candidate_generation'] = gen_stats
        
        # Phase 3: Filter and score
        recommendations, filter_stats = filter_and_score_candidates(
            candidates,
            export_loader,
            target_count=target
        )
        all_stats['filtering_scoring'] = filter_stats
        
        # Phase 4: Resolve and output
        playlist_id, tracks_added, output_stats = resolve_and_output(
            sp,
            recommendations,
            playlist_name
        )
        all_stats['resolution_output'] = output_stats
        
        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"Playlist: {playlist_id}")
        logger.info(f"Tracks added: {tracks_added}")
        logger.info(f"Total candidates: {gen_stats['total_candidates']}")
        logger.info(f"Filtered (played): {filter_stats['filtered_played']}")
        logger.info(f"Resolution rate: {output_stats['uris_resolved']}/{output_stats['recommendations_input']}")
        logger.info("=" * 60 + "\n")
        
        return {
            'success': True,
            'playlist_id': playlist_id,
            'tracks_added': tracks_added,
            'stats': all_stats
        }
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'stats': all_stats
        }
