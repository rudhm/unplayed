# Make.com Webhook Integration

## Overview

The Make.com webhook integration allows Unplayed to bypass Spotify API restrictions (including the 403 Forbidden errors for Premium-only endpoints and Developer account limitations) by routing playlist updates through Make.com's enterprise automation platform.

## How It Works

```
Unplayed Discovery Pipeline
         ↓
   (Last.fm Intelligence)
         ↓
   (Track Recommendations)
         ↓
   Make.com Webhook ───→ Spotify Integration
         ↓                      ↓
   Your Playlist! ←─────────────┘
```

**Benefits:**
- ✅ Works with Spotify Free accounts
- ✅ No Developer account required
- ✅ Bypasses 403 Forbidden errors
- ✅ Free tier available (1,000 operations/month)
- ✅ No code changes needed on Make.com side
- ✅ Automatic retry logic built-in

## Setup Instructions

### Step 1: Create Make.com Account

1. Go to [make.com](https://www.make.com)
2. Sign up for a free account (1,000 operations/month)
3. Verify your email

### Step 2: Create Webhook Scenario

1. Click **"Create a new scenario"**
2. Click the **"+"** button to add a module
3. Search for and select **"Webhooks"**
4. Choose **"Custom webhook"**
5. Click **"Add"** to create a new webhook
6. Name it: `Unplayed Track Receiver`
7. Click **"Save"**
8. **COPY THE WEBHOOK URL** - you'll need this! It looks like:
   ```
   https://hook.eu1.make.com/YOUR_UNIQUE_WEBHOOK_ID
   ```

### Step 3: Add Spotify Module

1. Click the **"+"** after the webhook module
2. Search for and select **"Spotify"**
3. Choose **"Add Track to a Playlist"**
4. Click **"Create a connection"** and authorize with your Spotify account
5. Configure the module:
   - **Playlist**: Select "Unplayed Discoveries" (or create it first in Spotify)
   - **Search Query**: Type: `{{1.track}}` (this pulls from the webhook)
   - **Artist** (optional): Type: `{{1.artist}}`
6. Click **"OK"**

### Step 4: Activate Scenario

1. Click the **"Scheduling"** toggle at the bottom
2. Choose **"Immediately as data arrives"** (default)
3. Click **"Save"** (icon in bottom-left)
4. Toggle the scenario **"ON"** (switch at bottom)

### Step 5: Configure Unplayed

Add the webhook URL to your environment:

```bash
export MAKE_WEBHOOK_URL="https://hook.eu1.make.com/YOUR_UNIQUE_WEBHOOK_ID"
```

Or add to your `.env` file:
```
MAKE_WEBHOOK_URL=https://hook.eu1.make.com/YOUR_UNIQUE_WEBHOOK_ID
```

### Step 6: Test It!

Run the test script:
```bash
python test_webhook.py
```

Or run the full pipeline:
```bash
python main.py
```

## Architecture

The webhook integration follows this flow:

```python
# Phase 4: Output Layer
export_to_make_webhook(
    recommendations=[
        {'artist': 'Artist Name', 'track': 'Track Name'},
        ...
    ],
    webhook_url="https://hook.eu1.make.com/...",
    playlist_name="Unplayed Discoveries"
)

# For each track:
# 1. POST to Make.com webhook: {"artist": "...", "track": "...", "is_first": true/false}
# 2. Make.com receives the data
# 3. Make.com searches Spotify
# 4. Make.com adds track to playlist
# 5. Return success/failure
# 
# The "is_first" flag is true only for the first track,
# allowing Make.com to perform special actions (e.g., clear playlist)
```

## Graceful Fallback Chain

Unplayed tries multiple output methods in priority order:

1. **Make.com Webhook** (primary) - If `MAKE_WEBHOOK_URL` is set
2. **Spotify API** (secondary) - If Make.com not configured
3. **IFTTT Webhook** (legacy) - If `IFTTT_WEBHOOK_KEY` is set
4. **Local File Export** (always works) - Markdown + CSV files

## Rate Limiting

The webhook exporter includes built-in rate limiting:
- 3 second delay between each track
- Automatic retry on failures
- Success/failure logging for each track

For 40 tracks, expect ~120 seconds (2 minutes) for the webhook phase.

## Webhook Payload Format

Each track is sent to Make.com with the following JSON payload:

```json
{
  "track": "Track Name",
  "artist": "Artist Name",
  "is_first": true  // true only for the first track, false for all others
}
```

The `is_first` flag can be used in Make.com to trigger special actions for the first track (e.g., clear the playlist, send a notification, etc.).

## Troubleshooting

### "No tracks sent successfully"
- **Check webhook URL**: Make sure you copied it correctly
- **Verify scenario is ON**: Check Make.com dashboard
- **Check Spotify connection**: Re-authorize if needed
- **Test with sample data**: Run `test_webhook.py` first

### "Partial success"
- **Rate limiting**: Some tracks may fail due to Make.com rate limits
- **Search failures**: Some track names don't match Spotify catalog
- **Network issues**: Temporary connectivity problems

### "Make.com webhook failed: ..."
- **Invalid URL**: Check that webhook URL is correct
- **Scenario inactive**: Make sure scenario is turned ON
- **Free tier limit**: You've exceeded 1,000 operations/month
- **Connection expired**: Re-authorize Spotify in Make.com

## Free Tier Limits

Make.com free tier includes:
- **1,000 operations/month**
- Each track = 1 operation
- 40 tracks/day = 1,200 operations/month (slightly over)

**Solution:** 
- Upgrade to paid plan ($9/month for 10,000 operations)
- Run less frequently (e.g., weekly instead of daily)
- Reduce target count (e.g., 25 tracks instead of 40)

## Advanced Configuration

### Custom Playlist Name

```python
pipeline_result = run_full_pipeline(
    sp=sp,
    playlist_name="My Custom Discovery Playlist",  # Change here
    target=40,
    make_webhook_url=make_webhook_url
)
```

Then update your Make.com scenario to use a different playlist.

### Multiple Playlists

Create multiple scenarios in Make.com, each with a different webhook URL and playlist:

```bash
export MAKE_WEBHOOK_URL_ROCK="https://hook.eu1.make.com/rock_webhook_id"
export MAKE_WEBHOOK_URL_JAZZ="https://hook.eu1.make.com/jazz_webhook_id"
```

### Webhook-Only Mode (No Spotify API)

If you don't have Spotify API credentials at all:

```python
# Skip Spotify authentication
# sp = None  # Not needed for webhook-only mode

pipeline_result = run_full_pipeline(
    sp=None,  # Webhook doesn't need Spotify API
    playlist_name="Unplayed Discoveries",
    target=40,
    make_webhook_url=os.getenv('MAKE_WEBHOOK_URL')
)
```

**Note:** This will skip URI resolution entirely and rely 100% on Make.com's Spotify search.

## Comparison: Make.com vs Direct Spotify API

| Feature | Make.com Webhook | Direct Spotify API |
|---------|-----------------|-------------------|
| Free account support | ✅ Yes | ❌ No (403 errors) |
| Developer account required | ❌ No | ✅ Yes |
| Setup complexity | Medium (5 min) | Easy (2 min) |
| Monthly limits | 1,000 ops (free) | Unlimited |
| Reliability | High | Medium (API changes) |
| Search accuracy | High (Spotify native) | High (Spotipy) |

## Migration from IFTTT

If you were previously using IFTTT:

1. Follow the Make.com setup above
2. Set `MAKE_WEBHOOK_URL` environment variable
3. Remove/keep `IFTTT_WEBHOOK_KEY` (used as fallback)
4. Run the pipeline - Make.com will be tried first

The pipeline will automatically prefer Make.com over IFTTT.

## Support

- **Make.com documentation**: https://www.make.com/en/help
- **Spotify integration guide**: https://www.make.com/en/integrations/spotify
- **Unplayed issues**: Create a GitHub issue in the repository

## Example Output

```
============================================================
PHASE 4: WEBHOOK EXPORT & PLAYLIST GENERATION
============================================================
Sending 40 tracks to automation pipeline...
Target playlist: Unplayed Discoveries
Webhook: https://hook.eu1.make.com/oew1k7uglnazdaiaw...
  → Progress: 10/40 tracks sent
  → Progress: 20/40 tracks sent
  → Progress: 30/40 tracks sent
  → Progress: 40/40 tracks sent
============================================================
✓ Pipeline Complete! Successfully routed 40/40 tracks to Spotify.
============================================================
```

## Next Steps

1. ✅ Complete the Make.com setup above
2. ✅ Test with `python test_webhook.py`
3. ✅ Run the full pipeline with `python main.py`
4. ✅ Check your Spotify playlist!
5. 📅 Schedule daily/weekly runs (optional)

Enjoy your personalized music discovery! 🎵
