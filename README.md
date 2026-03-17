# 🎧 Unplayed: Discover Songs You've Actually Never Heard

Spotify recommends songs you might like, but it still repeats artists you've already heard. I built Unplayed to discover songs I've never played before, using the Spotify API and an automated discovery engine.

The problem with Spotify's recommendations is real: you get stuck in loops with the same artists, the algorithm doesn't remember what you've actually played, and "personalized" starts to feel formulaic. This script solves that by building a hybrid system that reads your listening history, discovers new tracks from genres you love, and maintains a permanent memory of everything it's ever recommended—so you never get the same song twice.

## ✨ Features

**The Last.fm Bridge**: Spotify locked down their APIs, so we work around it. We map your top artists to Last.fm's open genre database to find what you actually want to hear.

**V2 Scoring Algorithm**: Evaluates 120+ candidate songs and ranks them using a custom formula that balances freshness (new songs) with what matches your taste.

**No Artist Fatigue**: Enforces a max of 2 songs per artist per discovery, so you don't get bored of the same band.

**80/20 Mix**: 80% laser-focused on your exact taste, 20% random wildcard picks to surprise you with something unexpected.

**True Unplayed Guarantee**: Uses a local SQLite database to remember every single song we've ever given you. Zero repeats. Ever.

## Setup Instructions

### Prerequisites

You'll need:
- **Python 3.11+** (this project uses `uv` for package management)
- **Spotify Developer App** (free at [developer.spotify.com](https://developer.spotify.com))
- **Last.fm API Key** (free at [last.fm/api](https://www.last.fm/api))

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
   SPOTIPY_CLIENT_ID=your_spotify_client_id
   SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
   LASTFM_API_KEY=your_lastfm_api_key
   ```

3. **Run locally:**
   ```bash
   python main.py
   ```
   
   On first run, your browser will open to authorize Spotify. This creates a `.cache` file for authentication.

### GitHub Actions Setup

To automate this with GitHub Actions, set these **Repository Secrets** (Settings → Secrets and variables → Actions):

| Secret Name | Source | Notes |
|---|---|---|
| `SPOTIPY_CLIENT_ID` | Spotify Dashboard | Your app's Client ID |
| `SPOTIPY_CLIENT_SECRET` | Spotify Dashboard | Your app's Client Secret |
| `SPOTIPY_REDIRECT_URI` | Fixed | Use `http://127.0.0.1:8888/callback` |
| `LASTFM_API_KEY` | Last.fm API | Your Last.fm API key |
| `SPOTIFY_CACHE_JSON` | Local `.cache` file | See below |

#### Storing SPOTIFY_CACHE_JSON

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

---

## Security Notes

- ✅ `.cache` and `.env` files are in `.gitignore` (never committed)
- ✅ GitHub Secrets are encrypted at rest and in transit
- ✅ Workflow logs don't display secret values
- ✅ Consider rotating credentials periodically
- ❌ Never hardcode tokens in your code or commit `.cache` files

For more details, see the [docs/](docs/) directory.
