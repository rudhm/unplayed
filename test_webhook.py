#!/usr/bin/env python3
"""
Test script for Make.com webhook integration.

This demonstrates the new webhook-based output method that bypasses
Spotify API restrictions.

Usage:
    export MAKE_WEBHOOK_URL="https://hook.eu1.make.com/YOUR_WEBHOOK_ID"
    python test_webhook.py
"""

import logging
from discovery import export_to_make_webhook

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_webhook_with_sample_data():
    """Test the webhook exporter with sample recommendations."""
    
    # Sample recommendations (similar to what the pipeline produces)
    sample_tracks = [
        {
            'artist': 'The Beatles',
            'artist_display': 'The Beatles',
            'track': 'Let It Be',
            'track_display': 'Let It Be',
            'score': 0.92
        },
        {
            'artist': 'Pink Floyd',
            'artist_display': 'Pink Floyd',
            'track': 'Wish You Were Here',
            'track_display': 'Wish You Were Here',
            'score': 0.89
        },
        {
            'artist': 'Led Zeppelin',
            'artist_display': 'Led Zeppelin',
            'track': 'Stairway to Heaven',
            'track_display': 'Stairway to Heaven',
            'score': 0.91
        }
    ]
    
    logger.info("Testing Make.com webhook with 3 sample tracks...")
    logger.info("=" * 60)
    
    # Test the webhook (using the default URL from the function)
    # Replace with your actual webhook URL!
    webhook_url = "https://hook.eu1.make.com/oew1k7uglnazdaiawavugih45kuov4d8"
    
    success_count = export_to_make_webhook(
        recommendations=sample_tracks,
        webhook_url=webhook_url,
        playlist_name="Test Playlist"
    )
    
    logger.info("=" * 60)
    logger.info(f"Test complete: {success_count}/{len(sample_tracks)} tracks sent successfully")
    
    if success_count == len(sample_tracks):
        logger.info("✓ All tracks sent successfully!")
        logger.info("Check your Spotify playlist to verify they were added.")
    elif success_count > 0:
        logger.warning(f"⚠ Partial success: {success_count}/{len(sample_tracks)} tracks sent")
    else:
        logger.error("✗ No tracks sent successfully. Check your webhook URL and Make.com scenario.")


if __name__ == "__main__":
    logger.info("Make.com Webhook Integration Test")
    logger.info("=" * 60)
    logger.info("This tests the webhook output method without running the full pipeline.")
    logger.info("")
    logger.info("IMPORTANT: Update the webhook_url variable with your actual URL!")
    logger.info("=" * 60)
    logger.info("")
    
    try:
        test_webhook_with_sample_data()
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        exit(1)
