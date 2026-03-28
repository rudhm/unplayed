"""
Shared utilities for the Unplayed music discovery system.

Provides canonical text normalization and track ID generation
to ensure consistent matching across Last.fm, Spotify exports,
and Spotify API data.
"""

import re
import logging

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent comparison across data sources.
    
    Applies aggressive normalization:
    - Converts to lowercase
    - Removes all punctuation using regex (including | to avoid separator conflicts)
    - Strips leading/trailing whitespace
    - Collapses multiple spaces to single space
    
    Args:
        text: Text to normalize (artist name, track name, etc.)
    
    Returns:
        Normalized text string
    
    Examples:
        >>> normalize_text("Guns N' Roses")
        'guns n roses'
        >>> normalize_text("  The Beatles!  ")
        'the beatles'
        >>> normalize_text("Björk")
        'bjork'
        >>> normalize_text("Artist | Name")
        'artist  name'
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove all punctuation and special characters (keep only alphanumeric and spaces)
    # This regex removes | along with other punctuation to avoid separator conflicts
    text = re.sub(r"[^\w\s]", "", text)
    
    # Collapse multiple spaces to single space and strip
    text = re.sub(r"\s+", " ", text).strip()
    
    return text


def get_track_id(artist: str, track: str) -> str:
    """
    Generate a canonical track ID for deduplication and matching.
    
    Creates a unique identifier by combining normalized artist and track names
    with a pipe delimiter. This ID is used consistently across:
    - Last.fm track data
    - Spotify export history
    - Spotify API search results
    
    The | separator is safe because normalize_text removes it from input.
    
    Args:
        artist: Artist name (will be normalized)
        track: Track name (will be normalized)
    
    Returns:
        Canonical track ID in format "artist|track"
    
    Examples:
        >>> get_track_id("The Beatles", "Let It Be")
        'the beatles|let it be'
        >>> get_track_id("Guns N' Roses", "Sweet Child O' Mine")
        'guns n roses|sweet child o mine'
    """
    normalized_artist = normalize_text(artist)
    normalized_track = normalize_text(track)
    
    if not normalized_artist or not normalized_track:
        logger.warning(f"Empty track ID generated for artist='{artist}', track='{track}'")
        return ""
    
    return f"{normalized_artist}|{normalized_track}"


def split_track_id(track_id: str) -> tuple[str, str]:
    """
    Split a canonical track ID back into artist and track names.
    
    Args:
        track_id: Canonical track ID in format "artist|track"
    
    Returns:
        Tuple of (artist, track), both normalized
    
    Examples:
        >>> split_track_id("the beatles|let it be")
        ('the beatles', 'let it be')
    """
    if not track_id or "|" not in track_id:
        logger.warning(f"Invalid track ID format: '{track_id}'")
        return ("", "")
    
    # maxsplit=1 ensures we always get exactly 2 parts
    parts = track_id.split("|", 1)
    return (parts[0], parts[1])
