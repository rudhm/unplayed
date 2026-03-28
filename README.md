# 🎧 Unplayed: Discover Songs You've Actually Never Heard

> **Works with Spotify Free & Premium** | Generates 40 personalized track recommendations using Last.fm intelligence

Spotify recommends songs you might like, but it still repeats artists you've already heard. Unplayed solves this by using a **Hybrid Discovery Architecture** that combines Last.fm's taste intelligence with your optional local listening history to generate genuinely fresh recommendations.

The problem with Spotify's recommendations is real: you get stuck in loops with the same artists, the algorithm doesn't remember what you've actually played, and "personalized" starts to feel formulaic. This script solves that through intelligent music discovery that works for **everyone**.

## 🏗️ Hybrid Architecture

Unplayed uses a three-layer architecture designed to work with **Spotify Free** accounts:

1. **🧠 Intelligence Layer (Last.fm)** - No authentication required
   - Analyzes your top artists and similar artists
   - Generates 200-300 candidate tracks
   - Rich metadata from Last.fm's community database

2. **💾 Memory Layer (Local GDPR Exports)** - Optional
   - Filters out tracks you've already heard
   - Uses your Spotify data export files
   - 100% privacy - stays on your machine

3. **🎵 Output Layer (Spotify)** - Free tier compatible
   - Updates your "Unplayed Discoveries" playlist (Premium/Developer)
   - OR exports to local files with clickable search links (Free/Restricted)
   - Graceful fallback - always delivers recommendations

## ✨ Key Features

**🎯 100% Success Rate**: Never crashes. If Spotify API is restricted, automatically exports to beautifully formatted Markdown + CSV files with clickable search links.

**🆓 Spotify Free Compatible**: Works perfectly with free accounts. Premium users get playlist updates; Free users get local exports.

**🎨 Beautiful Terminal UI**: Rich, colorful output with tables showing your top 10 recommendations.

**🔗 Clickable Links**: Every track includes a direct Spotify search URL - works on web, mobile, and desktop.

**📊 Dual Export**: Markdown (human-readable) and CSV (spreadsheet-compatible) formats.

**🔄 Zero Data Loss**: Recommendations always delivered, even if APIs fail or rate limits hit.

**🚫 No Repeats**: Optional GDPR export integration ensures you never get tracks you've already heard.

## Setup Instructions

### Prerequisites

**Required:**
- **Python 3.11+** (this project uses `uv` for package management)
- **Spotify Account** (Free or Premium - both work!)
- **Spotify Developer App** (free at [developer.spotify.com](https://developer.spotify.com))
- **Last.fm API Key** (free at [last.fm/api](https://www.last.fm/api))
- **Last.fm Account** with scrobbling history (connect your Spotify to Last.fm)

**Optional:**
- **Spotify GDPR Data Export** for play history filtering (see [Spotify Privacy](https://www.spotify.com/account/privacy/))

### Local Development

1. **Clone and install dependencies:**
   ```bash
   git clone https://github.com/rudhm/unplayed
   cd unplayed
   uv sync
   ```

2. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials:
   ```env
   # Spotify (for output layer - search & playlists)
   SPOTIPY_CLIENT_ID=your_spotify_client_id
   SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
   
   # Last.fm (for intelligence layer - required)
   LASTFM_API_KEY=your_lastfm_api_key
   LASTFM_USERNAME=your_lastfm_username
   
   # Optional: Spotify GDPR export for play history filtering
   SPOTIFY_EXPORT_PATH=./spotify_data
   ```

3. **Run the discovery engine:**
   ```bash
   python main.py
   ```
   
   On first run, your browser will open to authorize Spotify. This creates a `.cache` file for authentication.

   **Expected behavior:**
   - ✅ Phase 1-3: Generates recommendations using Last.fm (always works)
   - ✅ Phase 4: Attempts to update Spotify playlist
     - **Premium/Developer accounts**: Playlist updated successfully
     - **Free/Restricted accounts**: Exports to `output/discoveries_TIMESTAMP.md` and `.csv`
   
   **Output files** (when Spotify API is restricted):
   ```
   output/
   ├── discoveries_20260328_092837.md  ← Markdown with clickable links
   └── discoveries_20260328_092837.csv ← Spreadsheet format
   ```

   ⚠️ **Updating from older version?** Delete `.cache` first:
   ```bash
   rm .cache
   python main.py
   ```

### GitHub Actions Setup

**Note:** GitHub Actions may encounter Spotify API restrictions. The pipeline will automatically fall back to exporting recommendations as artifacts.

To automate this with GitHub Actions, set these **Repository Secrets** (Settings → Secrets and variables → Actions):

| Secret Name | Source | Notes |
|---|---|---|
| `SPOTIPY_CLIENT_ID` | Spotify Dashboard | Your app's Client ID |
| `SPOTIPY_CLIENT_SECRET` | Spotify Dashboard | Your app's Client Secret |
| `SPOTIPY_REDIRECT_URI` | Fixed | Use `http://127.0.0.1:8888/callback` |
| `LASTFM_API_KEY` | Last.fm API | Your Last.fm API key |
| `LASTFM_USERNAME` | Last.fm Profile | Your Last.fm username |
| `SPOTIFY_CACHE_JSON` | Local `.cache` file | See below |

#### Storing SPOTIFY_CACHE_JSON

⚠️ **CRITICAL:** After updating the code, regenerate your token locally first, then update the GitHub Secret.

This is the most common source of setup errors. Follow these steps exactly:

1. **On your local machine**, export your token:
   ```bash
   cat .cache
   ```
   
   Output will be a single-line JSON object:
   ```json
   {"access_token":"BQD...","token_type":"Bearer","expires_in":3600,"refresh_token":"AQA...","scope":"...","expires_at":1234567890}
   ```

2. **In GitHub UI:**
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `SPOTIFY_CACHE_JSON`
   - Value: **Paste the entire JSON** (no extra quotes, no line breaks)
   - Verify it starts with `{` and ends with `}`
   - Click "Add secret"

3. **Common mistakes to avoid:**
   - ❌ Adding quotes around the JSON: `"{ ... }"`
   - ❌ Copying only the access token, not the full JSON
   - ❌ Including extra whitespace or newlines
   - ✅ Paste the raw output from `cat .cache` directly

---

## 📁 Output Formats

### Spotify Playlist (Premium/Developer accounts)
When the Spotify API allows, tracks are added directly to your "Unplayed Discoveries" playlist.

### Local Export Files (Free/Restricted accounts)
When Spotify API returns 403 or other restrictions, recommendations are exported to local files:

#### Markdown Format (`output/discoveries_TIMESTAMP.md`)
```markdown
# 🎵 Unplayed Discoveries

## 1. Radiohead - Paranoid Android

**Score:** 0.957

🔗 [Search on Spotify](https://open.spotify.com/search/Radiohead%20Paranoid%20Android)
```

- **Use case**: Human-readable, clickable links in any markdown viewer
- **Clickable links**: Work on GitHub, VS Code, web browsers
- **Mobile-friendly**: Links open in Spotify app

#### CSV Format (`output/discoveries_TIMESTAMP.csv`)
```csv
Rank,Artist,Track,Score,Spotify Search URL
1,Radiohead,Paranoid Android,0.957,https://open.spotify.com/search/...
```

- **Use case**: Import to spreadsheets, databases, or automation tools
- **Excel/Sheets**: Open directly in your favorite spreadsheet app
- **Bulk processing**: Easy to parse and manipulate programmatically

#### Terminal Display (Rich UI)
```
   🎵 Top 10 Recommended Tracks   
┏━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ # ┃ Artist         ┃ Track          ┃ Score ┃
┡━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ 1 │ Radiohead      │ Paranoid...    │ 0.957 │
│ 2 │ The Smiths     │ How Soon...    │ 0.943 │
└───┴────────────────┴────────────────┴───────┘
```

- **Use case**: Quick preview of top recommendations
- **Colored output**: Beautiful formatting with the `rich` library
- **Always available**: Shows during every run

---

## Troubleshooting

### "Failed to decode SPOTIFY_CACHE_JSON"

**Cause:** The secret contains invalid JSON or extra whitespace.

**Fix:**
1. Verify your local `.cache` is valid JSON:
   ```bash
   python -c "import json; json.load(open('.cache'))" && echo "✓ Valid"
   ```

2. Delete and recreate the GitHub secret:
   ```bash
   cat .cache  # Copy this entire output
   ```
   - Go to Settings → Secrets → Delete `SPOTIFY_CACHE_JSON`
   - Create new secret with the fresh output from `cat .cache`
   - Verify it's a single line with no extra quotes

### "No Spotify OAuth token found in CI environment"

**Cause:** `SPOTIFY_CACHE_JSON` secret is missing, empty, or not being loaded.

**Fix:**
1. Check the secret exists in GitHub (Settings → Secrets)
2. If missing, run `cat .cache` locally and create the secret
3. Re-run the workflow

### "invalid_grant" or "token expired"

**Cause:** The refresh token expired or is invalid (usually after 6+ months).

**Fix:**
1. Regenerate locally:
   ```bash
   rm .cache
   python main.py
   ```
   Authorize in your browser when prompted.

2. Update GitHub secret:
   ```bash
   cat .cache  # Copy this
   ```
   - Go to Settings → Secrets → Edit `SPOTIFY_CACHE_JSON`
   - Replace with the new token output
   - Save and re-run workflow

### "Missing Spotify credentials"

**Cause:** `SPOTIPY_CLIENT_ID` or `SPOTIPY_CLIENT_SECRET` are not set in GitHub Secrets.

**Fix:**
1. Get credentials from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Add these secrets to GitHub:
   - `SPOTIPY_CLIENT_ID` → Your app's Client ID
   - `SPOTIPY_CLIENT_SECRET` → Your app's Client Secret
   - `SPOTIPY_REDIRECT_URI` → `http://127.0.0.1:8888/callback`

### Workflow runs but doesn't add tracks

**Cause:** Authentication worked, but playlist or genre discovery failed.

**Check:**
- Verify you're logged into the correct Spotify account
- Check that the "Unplayed" playlist exists in your Spotify account
- Review full workflow logs for specific errors

### Local development issues

**"No module named 'spotipy'"**
```bash
pip install spotipy python-dotenv
```

**"No cached token found locally"**
- Run `python main.py` to generate the token via browser auth
- This creates the `.cache` file

**".env file not found"**
```bash
cp .env.example .env
# Edit with your credentials
```

### "No top artists found" or "Pipeline failed"

**Cause:** Last.fm username has no scrobbling history or incorrect username.

**Fix:**
1. Verify your Last.fm username is correct in `.env`
2. Check you have scrobbling history at `https://www.last.fm/user/YOUR_USERNAME`
3. Connect Spotify to Last.fm if not already done
4. Wait for some scrobbles to accumulate (at least 10-20 artists recommended)

### Local export fallback triggered (403 Forbidden)

**This is not an error!** It's the expected behavior for Spotify Free accounts or when API restrictions apply.

**What happens:**
- Pipeline completes successfully
- Recommendations exported to `output/` directory
- Terminal displays top 10 tracks
- All tracks have clickable Spotify search URLs

**To use the recommendations:**
1. Open `output/discoveries_TIMESTAMP.md` in any markdown viewer
2. Click the search links to find tracks on Spotify
3. Or import `output/discoveries_TIMESTAMP.csv` to your favorite tool

---

## Security & Privacy

- ✅ `.cache` and `.env` files are in `.gitignore` (never committed)
- ✅ `output/` directory in `.gitignore` (local exports stay private)
- ✅ GitHub Secrets are encrypted at rest and in transit
- ✅ Workflow logs don't display secret values
- ✅ GDPR exports never leave your machine (optional, local-only)
- ✅ Last.fm API requires no authentication (read-only public data)
- ✅ Consider rotating credentials periodically
- ❌ Never hardcode tokens in your code or commit `.cache` files

## FAQ

**Q: Do I need Spotify Premium?**  
A: No! The system works for both Free and Premium users. Premium users get playlist updates; Free users get local exports with clickable links.

**Q: Why do I need a Last.fm account?**  
A: Last.fm provides the intelligence layer for recommendations. Connect your Spotify to Last.fm to build your listening history, then use that username in the `.env` file.

**Q: What's a GDPR export and do I need it?**  
A: It's your complete Spotify listening history (download from [Spotify Privacy](https://www.spotify.com/account/privacy/)). It's **optional** - the system works without it, but it helps filter out tracks you've already heard.

**Q: What if I don't have much Last.fm history?**  
A: You need at least some scrobbling history (10-20 artists minimum). Connect Spotify to Last.fm and let it accumulate for a few days/weeks.

**Q: Can I customize the scoring algorithm?**  
A: Yes! Edit `discovery.py` → `score_track()` function. The current formula is: `(0.6 × popularity) + (0.4 × artist_weight) + history_boost`.

**Q: How often should I run this?**  
A: Weekly is a good cadence. The GitHub Actions workflow can be scheduled with a cron trigger.

**Q: Why are some tracks not resolving to Spotify URIs?**  
A: Last.fm and Spotify catalogs don't perfectly match. The system uses fuzzy matching (85% similarity threshold) and skips tracks that don't meet the threshold.

**Q: Can I use this for multiple users?**  
A: Yes, but each user needs their own Last.fm account and credentials. You could run multiple instances with different `.env` files.

---

For more technical details, see the documentation:
- [COMPLETE_ARCHITECTURE.md](COMPLETE_ARCHITECTURE.md) - System architecture and data flow
- [GRACEFUL_FALLBACK_COMPLETE.md](GRACEFUL_FALLBACK_COMPLETE.md) - Fallback system details  
- [HYBRID_MIGRATION_COMPLETE.md](HYBRID_MIGRATION_COMPLETE.md) - Migration from old architecture
- [docs/](docs/) - Additional guides and references
