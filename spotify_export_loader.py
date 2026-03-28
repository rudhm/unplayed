import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime
from collections import Counter

from utils import normalize_text, get_track_id

logger = logging.getLogger(__name__)


class SpotifyExportLoader:
    """
    Loader for Spotify StreamingHistory*.json export files.
    
    This is OPTIONAL data source for personalization.
    Provides:
    - Played track filtering
    - Artist frequency weighting
    - Recency bias
    """
    
    def __init__(self, export_path: Optional[str] = None):
        """
        Initialize loader.
        
        Args:
            export_path: Path to directory containing StreamingHistory*.json files
                        or path to a single JSON file
        """
        self.export_path = export_path
        self.raw_data = []
        self.played_tracks = set()
        self.artist_frequencies = {}
        self.recent_tracks = []
        self.total_plays = 0
        self.date_range = None
        
        if export_path:
            self.load()
    
    def load(self) -> bool:
        """
        Load and parse StreamingHistory files.
        
        Returns:
            True if successfully loaded, False otherwise
        """
        if not self.export_path:
            logger.warning("No export path configured")
            return False
        
        path = Path(self.export_path)
        
        if not path.exists():
            logger.warning(f"Export path does not exist: {self.export_path}")
            return False
        
        json_files = []
        
        if path.is_file():
            if path.suffix == '.json':
                json_files = [path]
            else:
                logger.warning(f"Export path is not a JSON file: {self.export_path}")
                return False
        elif path.is_dir():
            json_files = sorted(path.glob('StreamingHistory*.json'))
            if not json_files:
                json_files = sorted(path.glob('*.json'))
        
        if not json_files:
            logger.warning(f"No JSON files found in {self.export_path}")
            return False
        
        logger.info(f"Loading {len(json_files)} Spotify export file(s)...")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.raw_data.extend(data)
                        logger.debug(f"Loaded {len(data)} entries from {json_file.name}")
                    else:
                        logger.warning(f"Unexpected format in {json_file.name}")
            except Exception as e:
                logger.error(f"Failed to load {json_file.name}: {e}")
        
        if not self.raw_data:
            logger.warning("No data loaded from export files")
            return False
        
        logger.info(f"Successfully loaded {len(self.raw_data)} play entries")
        
        self._process_data()
        return True
    
    def _process_data(self):
        """Process raw data to extract useful information."""
        if not self.raw_data:
            return
        
        play_times = []
        artist_plays = Counter()
        
        for entry in self.raw_data:
            artist_name = entry.get('artistName')
            track_name = entry.get('trackName')
            end_time = entry.get('endTime')
            ms_played = entry.get('msPlayed', 0)
            
            if not artist_name or not track_name:
                continue
            
            # Use canonical track ID generator
            track_key = get_track_id(artist_name, track_name)
            if track_key:
                self.played_tracks.add(track_key)
            
            normalized_artist = normalize_text(artist_name)
            
            if ms_played > 30000:
                artist_plays[normalized_artist] += 1
            
            if end_time:
                try:
                    play_time = datetime.fromisoformat(end_time.replace(' ', 'T'))
                    play_times.append((play_time, track_key))
                except (ValueError, AttributeError):
                    pass
        
        self.artist_frequencies = dict(artist_plays)
        self.total_plays = sum(artist_plays.values())
        
        if play_times:
            play_times.sort(reverse=True)
            self.recent_tracks = [track for _, track in play_times[:500]]
            
            earliest = min(p[0] for p in play_times)
            latest = max(p[0] for p in play_times)
            self.date_range = (earliest, latest)
        
        logger.info(
            f"Processed export data: "
            f"{len(self.played_tracks)} unique tracks, "
            f"{len(self.artist_frequencies)} artists, "
            f"{self.total_plays} total plays"
        )
        
        if self.date_range:
            logger.info(f"Date range: {self.date_range[0].date()} to {self.date_range[1].date()}")
    
    def is_track_played(self, artist: str, track: str) -> bool:
        """
        Check if a track has been played.
        
        Args:
            artist: Artist name (will be normalized)
            track: Track name (will be normalized)
        
        Returns:
            True if track was played, False otherwise
        """
        track_key = get_track_id(artist, track)
        return track_key in self.played_tracks if track_key else False
    
    def get_artist_frequency(self, artist: str) -> int:
        """
        Get play count for an artist.
        
        Args:
            artist: Artist name (will be normalized)
        
        Returns:
            Number of plays for this artist
        """
        return self.artist_frequencies.get(normalize_text(artist), 0)
    
    def get_artist_weight(self, artist: str) -> float:
        """
        Get normalized weight for an artist (0.0 to 1.0).
        
        Args:
            artist: Artist name (will be normalized)
        
        Returns:
            Weight between 0.0 (never played) and 1.0 (most played artist)
        """
        if self.total_plays == 0:
            return 0.0
        
        freq = self.get_artist_frequency(artist)
        
        if freq == 0:
            return 0.0
        
        max_freq = max(self.artist_frequencies.values()) if self.artist_frequencies else 1
        return freq / max_freq
    
    def is_recently_played(self, artist: str, track: str, recency_threshold: int = 100) -> bool:
        """
        Check if a track was played recently.
        
        Args:
            artist: Artist name (will be normalized)
            track: Track name (will be normalized)
            recency_threshold: Number of recent tracks to check
        
        Returns:
            True if track is in recent history, False otherwise
        """
        track_key = get_track_id(artist, track)
        return track_key in self.recent_tracks[:recency_threshold] if track_key else False
    
    def get_played_track_keys(self) -> Set[str]:
        """
        Get all played track keys.
        
        Returns:
            Set of track keys in format "artist|track" (normalized)
        """
        return self.played_tracks.copy()
    
    def get_top_artists(self, limit: int = 50) -> List[Tuple[str, int]]:
        """
        Get top artists by play count.
        
        Args:
            limit: Number of artists to return
        
        Returns:
            List of (artist_name, play_count) tuples, sorted by play count
        """
        sorted_artists = sorted(
            self.artist_frequencies.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_artists[:limit]
    
    def get_statistics(self) -> Dict:
        """
        Get summary statistics about the loaded data.
        
        Returns:
            Dict with statistics
        """
        return {
            'total_entries': len(self.raw_data),
            'unique_tracks': len(self.played_tracks),
            'unique_artists': len(self.artist_frequencies),
            'total_plays': self.total_plays,
            'date_range': {
                'start': self.date_range[0].isoformat() if self.date_range else None,
                'end': self.date_range[1].isoformat() if self.date_range else None
            } if self.date_range else None,
            'top_artist': max(self.artist_frequencies.items(), key=lambda x: x[1])[0] if self.artist_frequencies else None,
            'loaded': bool(self.raw_data)
        }
    
    def filter_unplayed_tracks(self, tracks: List[Dict]) -> List[Dict]:
        """
        Filter a list of tracks to only include unplayed ones.
        
        Args:
            tracks: List of track dicts with 'artist' and 'track' keys (normalized)
        
        Returns:
            Filtered list of unplayed tracks
        """
        if not self.played_tracks:
            return tracks
        
        filtered = []
        for track in tracks:
            artist = track.get('artist', '')
            track_name = track.get('track', '')
            if not self.is_track_played(artist, track_name):
                filtered.append(track)
        
        return filtered
    
    def has_data(self) -> bool:
        """Check if export data was successfully loaded."""
        return bool(self.raw_data)


def load_spotify_export(export_path: Optional[str] = None) -> Optional[SpotifyExportLoader]:
    """
    Factory function to load Spotify export with path from environment.
    
    Args:
        export_path: Path to export files (defaults to SPOTIFY_EXPORT_PATH env var)
    
    Returns:
        SpotifyExportLoader instance if loaded successfully, None otherwise
    """
    export_path = export_path or os.getenv('SPOTIFY_EXPORT_PATH')
    
    if not export_path:
        logger.info("No Spotify export path configured (SPOTIFY_EXPORT_PATH not set)")
        return None
    
    loader = SpotifyExportLoader(export_path)
    
    if not loader.has_data():
        logger.warning("Failed to load Spotify export data")
        return None
    
    logger.info("✓ Spotify export data loaded successfully")
    logger.info(f"  - {loader.get_statistics()['unique_tracks']} unique tracks")
    logger.info(f"  - {loader.get_statistics()['unique_artists']} unique artists")
    
    return loader
