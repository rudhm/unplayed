"""
Hybrid Discovery Engine for Unplayed.

Architecture:
1. INTELLIGENCE (Brain): Last.fm API for taste profiles and candidate generation
2. MEMORY (History): Local Spotify GDPR exports for filtering played tracks
3. OUTPUT (Resolution): Multiple output options with graceful fallback
   - Option A: Spotify API (search & playlists)
   - Option B: IFTTT Webhook (bypasses Premium restrictions)
   - Option C: Local file export (always works)

This design eliminates the 403 Forbidden errors from Spotify's user data endpoints
by using Last.fm as the primary intelligence layer and providing multiple output paths.
"""

import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
from functools import wraps
import time
import os
import csv
from urllib.parse import quote
import requests

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from lastfm_client import get_lastfm_client
from spotify_export_loader import load_spotify_export
from utils import get_track_id

logger = logging.getLogger(__name__)
console = Console() if RICH_AVAILABLE else None


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
        return {}, stats
    
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
    tracks_per_artist: int = 20,
    max_candidates: int = 600
) -> Tuple[List[Dict], Dict]:
    """
    Generate candidate tracks from artist pool using Last.fm.
    
    Strategy:
    1. For each artist in pool, fetch top tracks (deeper limit for discovery)
    2. Collect metadata: playcount, listeners, artist weight
    3. Return candidate list (500-600 tracks)
    
    Args:
        lastfm_client: Configured LastFmClient instance
        artist_pool: Dict of artist_name -> metadata from build_taste_profile
        tracks_per_artist: Number of tracks to fetch per artist (default 20 for deep cuts)
        max_candidates: Maximum total candidates to generate
    """
    logger.info("=" * 60)
    logger.info("PHASE 2: GENERATING CANDIDATES (DEEP CUTS)")
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
    
    logger.info(f"Fetching top {tracks_per_artist} tracks for {len(sorted_artists)} artists...")
    
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
            
            # Identify "Deep Cuts": Skip the top 2 global hits if the artist is popular
            # This ensures we don't just get the most obvious radio hits
            start_idx = 0
            if len(tracks) > 5:
                # If artist is very popular, skip the biggest hits
                first_track_listeners = tracks[0].get('listeners', 0)
                if first_track_listeners > 1000000:
                    start_idx = 3
                    logger.debug(f"  Skipping top hits for popular artist: {display_name}")
            
            for track_data in tracks[start_idx:]:
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
                    'source': artist_meta.get('source', 'unknown'),
                    'rank': tracks.index(track_data) + 1
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
    - base_score: (0.2 * popularity) + (0.8 * artist_weight)
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
    
    # Popularity score (normalized from listeners)
    # Reduced weight for popularity to favor personal taste
    popularity_score = min(1.0, listeners / 200000.0) if listeners > 0 else 0.0
    
    # Base score: 20% popularity (global), 80% artist weight (personal)
    # This shifts the focus from "Global Hits" to "Your Artists"
    base_score = (0.2 * popularity_score) + (0.8 * artist_weight)
    
    # History boost: If this artist is in user's Spotify history, boost score
    history_boost = 0.0
    if boost_history_artists and export_loader and export_loader.has_data():
        artist = track_data.get('artist', '')
        artist_freq = export_loader.get_artist_frequency(artist)
        if artist_freq > 0:
            # Boost by up to 0.2 based on how often artist is played
            history_artist_weight = export_loader.get_artist_weight(artist)
            history_boost = 0.2 * history_artist_weight
    
    return base_score + history_boost


def filter_and_score_candidates(
    candidates: List[Dict],
    export_loader,
    lastfm_client=None,
    target_count: int = 40,
    check_lastfm_playcount: bool = True
) -> Tuple[List[Dict], Dict]:
    """
    Filter, score, and select candidates using Diversity-Aware Round-Robin.
    
    Process:
    1. Filter out tracks in play history (local exports)
    2. Score remaining tracks (Artist Weight 80%, Popularity 20%)
    3. Group tracks by artist
    4. Apply Artist Slot Budgeting (Max 2 for Top Artists, 1 for Similar)
    5. Round-Robin selection until target_count is reached
    6. Verify unplayed status on Last.fm for final selection
    
    Args:
        candidates: List of candidate track dicts
        export_loader: SpotifyExportLoader instance (optional)
        lastfm_client: LastFmClient instance (optional)
        target_count: Number of tracks to return
        check_lastfm_playcount: If True, verify tracks are unplayed on Last.fm
    """
    logger.info("=" * 60)
    logger.info("PHASE 3: DIVERSITY-AWARE FILTERING & SELECTION")
    logger.info("=" * 60)
    
    stats = {
        'candidates_input': len(candidates),
        'filtered_played': 0,
        'filtered_lastfm_played': 0,
        'scored_tracks': 0,
        'final_count': 0
    }
    
    # Step 1: Filter out played tracks from export data
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
        logger.info(f"✓ Filtered {stats['filtered_played']} played tracks from exports")
    else:
        logger.warning("No export data - skipping Spotify play history filtering")
        unplayed = candidates
    
    if not unplayed:
        logger.error("No unplayed tracks remaining after filtering!")
        return [], stats
    
    # Step 2: Score all tracks
    for candidate in unplayed:
        candidate['score'] = score_track(candidate, export_loader)
    stats['scored_tracks'] = len(unplayed)
    
    # Step 3: Group tracks by artist and sort each artist's tracks by score
    artist_groups = {}
    for track in unplayed:
        artist = track.get('artist', 'Unknown')
        if artist not in artist_groups:
            artist_groups[artist] = []
        artist_groups[artist].append(track)
    
    for artist in artist_groups:
        artist_groups[artist].sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Step 4 & 5: Round-Robin selection with Artist Slot Budgeting
    # Sort artists by their highest-scoring track to prioritize favorites in the first rounds
    sorted_artists = sorted(
        artist_groups.keys(),
        key=lambda a: artist_groups[a][0]['score'],
        reverse=True
    )
    
    selected_tracks = []
    artist_counts = {artist: 0 for artist in sorted_artists}
    
    # Determine slot budget for each artist
    # Top artists get 2 slots, similar/discovery artists get 1
    def get_budget(artist_name):
        first_track = artist_groups[artist_name][0]
        return 2 if first_track.get('source') == 'top_artist' else 1

    logger.info(f"Starting Diversity-Aware Round-Robin (Target: {target_count})...")
    
    round_num = 1
    while len(selected_tracks) < target_count * 2 and any(len(artist_groups[a]) > 0 for a in sorted_artists):
        tracks_added_this_round = 0
        
        for artist in sorted_artists:
            if len(selected_tracks) >= target_count * 2:
                break
                
            # Skip if artist has reached their budget or has no more tracks
            if artist_counts[artist] >= get_budget(artist) or not artist_groups[artist]:
                continue
            
            # Take the next best track for this artist
            track = artist_groups[artist].pop(0)
            selected_tracks.append(track)
            artist_counts[artist] += 1
            tracks_added_this_round += 1
            
        if tracks_added_this_round == 0:
            break
            
        logger.debug(f"  Round {round_num}: Added {tracks_added_this_round} tracks")
        round_num += 1

    # Step 6: Verify unplayed status on Last.fm for top candidates
    final_tracks = []
    if check_lastfm_playcount and lastfm_client and lastfm_client.username:
        logger.info(f"Verifying top {len(selected_tracks)} candidates on Last.fm...")
        
        for candidate in selected_tracks:
            artist = candidate.get('artist_display', candidate.get('artist', ''))
            track = candidate.get('track_display', candidate.get('track', ''))
            
            playcount = lastfm_client.get_user_track_playcount(artist, track)
            
            if playcount > 0:
                stats['filtered_lastfm_played'] += 1
                continue
            
            final_tracks.append(candidate)
            if len(final_tracks) >= target_count:
                break
        
        logger.info(f"✓ Last.fm check: Filtered {stats['filtered_lastfm_played']} scrobbled tracks")
    else:
        final_tracks = selected_tracks[:target_count]
    
    stats['final_count'] = len(final_tracks)
    logger.info(f"✓ Selected {len(final_tracks)} diverse tracks across {len(set(t['artist'] for t in final_tracks))} artists")
    
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


def send_to_ifttt_webhook(
    recommendations: List[Dict],
    webhook_key: str,
    event_name: str = "add_unplayed_track",
    batch_delay: float = 1.0
) -> int:
    """
    Send recommendations to IFTTT webhook for Spotify playlist management.
    
    IFTTT Setup:
    1. Create applet at ifttt.com/create
    2. IF: Webhooks - Receive a web request
       - Event Name: add_unplayed_track
    3. THEN: Spotify - Add track to playlist
       - Search Query: {{Value1}} {{Value2}}
       - Playlist: Unplayed Discoveries
    4. Get your webhook key from: ifttt.com/maker_webhooks/settings
    
    Args:
        recommendations: List of track dicts with artist/track keys
        webhook_key: Your IFTTT webhook key
        event_name: IFTTT event name (default: add_unplayed_track)
        batch_delay: Delay between requests in seconds (default: 1.0)
    
    Returns:
        Number of tracks successfully sent to IFTTT
    """
    if not webhook_key or webhook_key == "your_ifttt_webhook_key":
        logger.warning("IFTTT webhook key not configured - skipping IFTTT integration")
        return 0
    
    webhook_url = f"https://maker.ifttt.com/trigger/{event_name}/with/key/{webhook_key}"
    success_count = 0
    
    logger.info(f"Sending {len(recommendations)} tracks to IFTTT webhook...")
    
    for i, track in enumerate(recommendations, 1):
        try:
            artist = track.get('artist_display', track.get('artist', 'Unknown'))
            track_name = track.get('track_display', track.get('track', 'Unknown'))
            score = track.get('score', 0.0)
            
            payload = {
                "value1": artist,
                "value2": track_name,
                "value3": f"{score:.3f}"
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                success_count += 1
                if i % 10 == 0:  # Log progress every 10 tracks
                    logger.info(f"  Sent {i}/{len(recommendations)} tracks to IFTTT")
            else:
                logger.warning(f"IFTTT webhook returned {response.status_code} for: {artist} - {track_name}")
            
            # Rate limiting - be nice to IFTTT
            if i < len(recommendations):
                time.sleep(batch_delay)
        
        except Exception as e:
            logger.warning(f"Failed to send track {i} to IFTTT: {e}")
            continue
    
    logger.info(f"✓ Sent {success_count}/{len(recommendations)} tracks to IFTTT webhook")
    return success_count


def export_to_make_webhook(
    recommendations: List[Dict],
    webhook_url: str = "https://hook.eu1.make.com/oew1k7uglnazdaiawavugih45kuov4d8",
    playlist_name: str = "Unplayed Discoveries"
) -> int:
    """
    Phase 4: Output Layer (Make.com Webhook)
    
    Bypasses the Spotify Developer 403 Premium restriction by handing 
    the tracks off to a free Make.com enterprise automation.
    
    Make.com Setup:
    1. Create a webhook scenario at make.com
    2. Add webhook trigger module to receive JSON: {track: string, artist: string}
    3. Add Spotify "Add Track to Playlist" module
    4. Connect them and activate the scenario
    5. Use the webhook URL provided by Make.com
    
    Args:
        recommendations: List of track dicts with artist/track keys
        webhook_url: Your Make.com webhook URL
        playlist_name: Name of the playlist (for logging only)
    
    Returns:
        Number of tracks successfully sent to Make.com
    """
    logger.info("=" * 60)
    logger.info("PHASE 4: WEBHOOK EXPORT & PLAYLIST GENERATION")
    logger.info("=" * 60)
    
    if not webhook_url or "YOUR_WEBHOOK_URL" in webhook_url:
        logger.error("Make.com webhook URL not configured!")
        return 0
    
    logger.info(f"Sending {len(recommendations)} tracks to automation pipeline...")
    logger.info(f"Target playlist: {playlist_name}")
    logger.info(f"Webhook: {webhook_url[:50]}...")
    
    success_count = 0
    
    # Use enumerate to keep track of the index (0, 1, 2, 3...)
    for index, track in enumerate(recommendations):
        track_name = track.get("track_display", track.get("track", "Unknown Track"))
        artist_name = track.get("artist_display", track.get("artist", "Unknown Artist"))
        
        payload = {
            "track": track_name,
            "artist": artist_name,
            "is_first": index == 0  # True for the 1st track, False for the rest
        }
        
        try:
            # Send the data to Make.com
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            success_count += 1
            logger.info(f"  → Success: {artist_name} - {track_name}")
            
        except Exception as e:
            logger.warning(f"  → Failed to send '{artist_name} - {track_name}': {e}")
            
        time.sleep(3)
    
    logger.info("=" * 60)
    logger.info(f"✓ Pipeline Complete! Successfully routed {success_count}/{len(recommendations)} tracks to Spotify.")
    logger.info("=" * 60)
    
    return success_count


def export_to_local_file(
    recommendations: List[Dict],
    output_dir: str = "output",
    format: str = "markdown"
) -> str:
    """
    Export recommendations to local file as fallback when Spotify API fails.
    
    Args:
        recommendations: List of track dicts with artist/track/score keys
        output_dir: Directory to save file
        format: 'markdown' or 'csv'
    
    Returns:
        Path to exported file
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if format == "markdown":
        filepath = os.path.join(output_dir, f"discoveries_{timestamp}.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# 🎵 Unplayed Discoveries\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total recommendations: {len(recommendations)}\n\n")
            f.write("---\n\n")
            
            for i, track in enumerate(recommendations, 1):
                artist = track.get('artist_display', track.get('artist', 'Unknown'))
                track_name = track.get('track_display', track.get('track', 'Unknown'))
                score = track.get('score', 0.0)
                
                # Generate Spotify search URL
                search_query = f"{artist} {track_name}"
                encoded_query = quote(search_query)
                spotify_url = f"https://open.spotify.com/search/{encoded_query}"
                
                f.write(f"## {i}. {artist} - {track_name}\n\n")
                f.write(f"**Score:** {score:.3f}\n\n")
                f.write(f"🔗 [Search on Spotify]({spotify_url})\n\n")
                f.write("---\n\n")
    
    else:  # CSV format
        filepath = os.path.join(output_dir, f"discoveries_{timestamp}.csv")
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rank', 'Artist', 'Track', 'Score', 'Spotify Search URL'])
            
            for i, track in enumerate(recommendations, 1):
                artist = track.get('artist_display', track.get('artist', 'Unknown'))
                track_name = track.get('track_display', track.get('track', 'Unknown'))
                score = track.get('score', 0.0)
                
                search_query = f"{artist} {track_name}"
                encoded_query = quote(search_query)
                spotify_url = f"https://open.spotify.com/search/{encoded_query}"
                
                writer.writerow([i, artist, track_name, f"{score:.3f}", spotify_url])
    
    logger.info(f"✓ Exported {len(recommendations)} tracks to {filepath}")
    return filepath


def display_recommendations_terminal(recommendations: List[Dict], exported_file: str = None):
    """
    Display top recommendations in a rich terminal format.
    
    Args:
        recommendations: List of track dicts
        exported_file: Path to exported file
    """
    if not RICH_AVAILABLE or not console:
        # Fallback to simple print
        logger.info("=" * 60)
        logger.info("TOP 10 RECOMMENDATIONS")
        logger.info("=" * 60)
        for i, track in enumerate(recommendations[:10], 1):
            artist = track.get('artist_display', track.get('artist', 'Unknown'))
            track_name = track.get('track_display', track.get('track', 'Unknown'))
            score = track.get('score', 0.0)
            logger.info(f"{i:2d}. {artist} - {track_name} (score: {score:.3f})")
        logger.info("=" * 60)
        if exported_file:
            logger.info(f"\n📁 Full list exported to: {exported_file}")
        return
    
    # Rich table display
    table = Table(title="🎵 Top 10 Recommended Tracks", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Artist", style="cyan", no_wrap=False)
    table.add_column("Track", style="green", no_wrap=False)
    table.add_column("Score", justify="right", style="yellow")
    
    for i, track in enumerate(recommendations[:10], 1):
        artist = track.get('artist_display', track.get('artist', 'Unknown'))
        track_name = track.get('track_display', track.get('track', 'Unknown'))
        score = track.get('score', 0.0)
        table.add_row(str(i), artist, track_name, f"{score:.3f}")
    
    console.print("\n")
    console.print(table)
    
    if exported_file:
        console.print("\n")
        console.print(Panel(
            f"[bold green]✓ Full recommendations exported![/bold green]\n\n"
            f"📁 File: [cyan]{exported_file}[/cyan]\n"
            f"📊 Total tracks: [yellow]{len(recommendations)}[/yellow]\n\n"
            f"[dim]Open the file to see clickable Spotify search links for all tracks.[/dim]",
            title="Export Complete",
            border_style="green"
        ))


def resolve_and_output(
    recommendations: List[Dict],
    playlist_name: str = "Unplayed Discoveries",
    make_webhook_url: Optional[str] = None
) -> Tuple[str, int, Dict]:
    """
    Output tracks via Make.com webhook.
    
    Args:
        recommendations: List of track dicts with artist/track keys
        playlist_name: Name for the output playlist
        make_webhook_url: Make.com webhook URL (required)
    
    Returns:
        Tuple of (playlist_id, tracks_added, stats dict)
    """
    logger.info("=" * 60)
    logger.info("PHASE 4: OUTPUT & DELIVERY")
    logger.info("=" * 60)
    
    stats = {
        'recommendations_input': len(recommendations),
        'tracks_added': 0,
        'output_method': 'make_webhook',
        'make_webhook_used': True,
        'make_success': 0,
        'fallback_file': None
    }
    
    # Validate webhook URL is configured
    if not make_webhook_url or "YOUR_WEBHOOK_URL" in make_webhook_url:
        logger.error("Make.com webhook URL not configured!")
        logger.error("Set MAKE_WEBHOOK_URL environment variable.")
        return "", 0, stats
    
    # Send tracks to Make.com webhook
    try:
        logger.info("=" * 60)
        logger.info("OUTPUT METHOD: MAKE.COM WEBHOOK")
        logger.info("=" * 60)
        
        make_success = export_to_make_webhook(
            recommendations,
            webhook_url=make_webhook_url,
            playlist_name=playlist_name
        )
        
        stats['make_success'] = make_success
        stats['tracks_added'] = make_success
        
        if make_success > 0:
            # Also export for reference
            md_file = export_to_local_file(recommendations, format="markdown")
            stats['fallback_file'] = md_file
            
            logger.info(f"✓ Reference file created: {md_file}")
            
            # Display terminal summary
            display_recommendations_terminal(recommendations, md_file)
            
            return "MAKE_WEBHOOK", make_success, stats
        else:
            logger.error("Make.com webhook returned 0 successes")
            return "", 0, stats
            
    except Exception as make_error:
        logger.error(f"Make.com webhook failed: {make_error}", exc_info=True)
        return "", 0, stats


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
        lastfm_client=lastfm_client,
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


def run_full_pipeline(
    playlist_name: str = "Unplayed Discoveries",
    target: int = 40,
    make_webhook_url: Optional[str] = None
):
    """
    Run the complete discovery pipeline with Make.com webhook output.
    
    This is the main entry point that uses Last.fm for intelligence
    and Make.com webhook for output.
    
    Output method:
    - Make.com Webhook (required) - bypasses all API restrictions
    
    Args:
        playlist_name: Name for output playlist
        target: Target number of recommendations
        make_webhook_url: Make.com webhook URL (required)
    
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
            lastfm_client=lastfm_client,
            target_count=target
        )
        all_stats['filtering_scoring'] = filter_stats
        
        # Phase 4: Output via Make.com webhook
        playlist_id, tracks_added, output_stats = resolve_and_output(
            recommendations,
            playlist_name,
            make_webhook_url
        )
        all_stats['resolution_output'] = output_stats
        
        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE!")
        logger.info("=" * 60)
        
        output_method = output_stats.get('output_method', 'unknown')
        
        # Make.com webhook used
        logger.info(f"Output: Make.com Webhook")
        logger.info(f"Tracks sent to Make.com: {output_stats.get('make_success', 0)}/{output_stats['recommendations_input']}")
        logger.info(f"Reference file: {output_stats.get('fallback_file', 'N/A')}")
        
        logger.info(f"Total candidates: {gen_stats['total_candidates']}")
        logger.info(f"Filtered (played): {filter_stats['filtered_played']}")
        logger.info("=" * 60 + "\n")
        
        return {
            'success': True,
            'playlist_id': playlist_id,
            'tracks_added': tracks_added,
            'output_method': output_method,
            'stats': all_stats,
            'make_webhook_used': output_stats.get('make_webhook_used', False),
            'export_files': {
                'markdown': output_stats.get('fallback_file'),
                'csv': output_stats.get('fallback_csv')
            } if output_stats.get('fallback_file') else None
        }
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'stats': all_stats
        }
