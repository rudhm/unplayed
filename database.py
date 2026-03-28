import sqlite3
import logging

logger = logging.getLogger(__name__)

DB = "history.db"


def init_db():
    """
    Initialize the history database.
    
    Note: In the Hybrid Architecture, the played_tracks table is no longer
    populated from Spotify API (which requires Premium). Instead, play history
    comes from local GDPR exports loaded by SpotifyExportLoader.
    
    This table structure is kept for backward compatibility and future use.
    """
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS played_tracks (
            track_id TEXT PRIMARY KEY,
            artist_id TEXT,
            album_id TEXT,
            played_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS discovery_stats (
            run_id TEXT PRIMARY KEY,
            run_date TEXT,
            total_tracks_played INTEGER,
            unique_artists INTEGER,
            new_tracks_added INTEGER,
            filtered_count INTEGER,
            top_artists_used INTEGER DEFAULT 0,
            followed_artists_used INTEGER DEFAULT 0,
            saved_tracks_used INTEGER DEFAULT 0,
            playlists_used INTEGER DEFAULT 0,
            api_failures TEXT DEFAULT ''
        )
        """)

        conn.commit()


def track_exists(track_id):
    """
    Check if a track has already been played by the user.
    
    Args:
        track_id: Spotify track ID
    
    Returns:
        bool: True if track exists in played_tracks table
    """
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM played_tracks WHERE track_id = ? LIMIT 1", (track_id,))
        return cur.fetchone() is not None


def get_played_tracks():
    """
    Get all track IDs that have been played by the user.
    
    Returns:
        set: Set of all track_ids in played_tracks table
    """
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("SELECT track_id FROM played_tracks")
        return {row[0] for row in cur.fetchall()}


def get_stats():
    """
    Get listening analytics from the history database.
    
    Returns:
        dict: Statistics including:
            - total_tracks_played: Total number of distinct tracks ever played
            - unique_artists: Number of unique artists in play history
            - most_played_artists: List of top 3 artists by play count
            - discovery_rate: (new tracks added) / (total tracks played)
    """
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()

        # Total unique tracks played
        cur.execute("SELECT COUNT(*) FROM played_tracks")
        total_tracks = cur.fetchone()[0] or 0

        # Unique artists
        cur.execute("SELECT COUNT(DISTINCT artist_id) FROM played_tracks")
        unique_artists = cur.fetchone()[0] or 0

        # Most played artists (based on how many tracks from them are in history)
        cur.execute("""
            SELECT artist_id, COUNT(*) as count 
            FROM played_tracks 
            GROUP BY artist_id 
            ORDER BY count DESC 
            LIMIT 3
        """)
        most_played = [row[0] for row in cur.fetchall()]

        # Latest run stats (to calculate discovery rate)
        cur.execute("""
            SELECT new_tracks_added FROM discovery_stats 
            ORDER BY run_date DESC LIMIT 1
        """)
        new_tracks_last_run = cur.fetchone()
        new_tracks_last_run = new_tracks_last_run[0] if new_tracks_last_run else 0

        discovery_rate = (new_tracks_last_run / total_tracks) if total_tracks > 0 else 0

        return {
            "total_tracks_played": total_tracks,
            "unique_artists": unique_artists,
            "most_played_artists": most_played,
            "discovery_rate": round(discovery_rate, 3),
            "new_tracks_added": new_tracks_last_run
        }


def log_run_stats(run_id, new_tracks_added, filtered_count, api_stats=None):
    """
    Log statistics for a discovery run.
    
    Args:
        run_id: Unique identifier for this run
        new_tracks_added: Number of new tracks added to playlist
        filtered_count: Number of tracks filtered out as already-played
        api_stats: Dict with API success/failure metrics
    """
    from datetime import datetime
    
    if api_stats is None:
        api_stats = {}
    
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        
        stats = get_stats()
        
        cur.execute("""
            INSERT INTO discovery_stats 
            (run_id, run_date, total_tracks_played, unique_artists, new_tracks_added, filtered_count,
             top_artists_used, followed_artists_used, saved_tracks_used, playlists_used, api_failures)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            datetime.utcnow().isoformat(),
            stats["total_tracks_played"],
            stats["unique_artists"],
            new_tracks_added,
            filtered_count,
            1 if api_stats.get('top_artists_used', False) else 0,
            1 if api_stats.get('followed_artists_used', False) else 0,
            1 if api_stats.get('saved_tracks_used', False) else 0,
            1 if api_stats.get('playlists_used', False) else 0,
            ','.join(api_stats.get('api_failures', []))
        ))
        
        conn.commit()
        
        logger.info(
            f"Run stats logged - "
            f"Total tracks played: {stats['total_tracks_played']}, "
            f"Unique artists: {stats['unique_artists']}, "
            f"New tracks added: {new_tracks_added}, "
            f"Filtered out: {filtered_count}, "
            f"APIs used: {sum([api_stats.get(k, False) for k in ['top_artists_used', 'followed_artists_used', 'saved_tracks_used', 'playlists_used']])}/4, "
            f"Failures: {len(api_stats.get('api_failures', []))}"
        )
