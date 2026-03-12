# GitHub Actions Automation Setup

## Overview

The Spotify Discovery Engine now supports automatic playlist refresh via GitHub Actions. The workflow runs every 6 hours on GitHub's servers, keeping your playlist fresh without requiring your computer to be on.

## What's New

### Files Created/Modified

1. **`.github/workflows/discovery.yml`** (NEW)
   - Defines the GitHub Actions workflow
   - Runs every 6 hours on schedule
   - Allows manual triggering from Actions tab
   - Sets up Python environment and runs the discovery engine

2. **`spotify_client.py`** (MODIFIED)
   - Added CI/CD environment detection
   - Gracefully handles headless execution
   - Uses cached OAuth tokens (from `.cache` file)
   - Sets `open_browser=False` when running in GitHub Actions

3. **`.gitignore`** (MODIFIED)
   - Updated to TRACK `.cache` file (instead of ignoring it)
   - `.cache` contains your OAuth token needed for CI/CD authentication
   - Still ignores `.env` file (for local credentials)

4. **`README.md`** (MODIFIED)
   - Added complete GitHub Actions setup instructions
   - Documents how to add GitHub Secrets
   - Explains the first-run local authorization requirement

5. **`main.py`** (MODIFIED)
   - Removed hardcoded `num_searches=5` parameter
   - Now uses default value from discovery.py (2 searches)
   - Cleaner, more maintainable code

## Setup Instructions

### Step 1: Generate OAuth Token Locally (One-Time)

The workflow needs a cached OAuth token to run on GitHub. Generate it locally:

```bash
uv run main.py
```

This will:
1. Open your browser to authorize with Spotify
2. Create a `.cache` file with your OAuth token
3. Run the discovery engine

### Step 2: Commit the `.cache` File

The cached token is now stored in `.cache`. Commit it to GitHub:

```bash
git add .cache
git commit -m "Add cached OAuth token for GitHub Actions"
git push
```

⚠️ **Security Note**: The `.cache` file is your OAuth token. It's specific to your Spotify app credentials. Only commit it if:
- You're the sole user of the repository
- You haven't shared your credentials publicly
- You trust GitHub's security

### Step 3: Add GitHub Secrets

Go to your GitHub repository:

1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add three secrets:

| Name | Value |
|------|-------|
| `SPOTIPY_CLIENT_ID` | Your Spotify Client ID |
| `SPOTIPY_CLIENT_SECRET` | Your Spotify Client Secret |
| `SPOTIPY_REDIRECT_URI` | `http://localhost:8888/callback` |

**How to find your credentials:**
- Go to https://developer.spotify.com/dashboard
- Click your app
- Copy "Client ID"
- Click "Show Client Secret"

### Step 4: Verify the Workflow

Go to **Actions** tab in your GitHub repository. You should see:
- Workflow name: "Spotify Discovery Engine"
- Last run status
- Schedule: Every 6 hours

## How It Works

### Scheduled Runs

The workflow runs automatically on this schedule:

```
0 */6 * * *  (every 6 hours at UTC 0, 6, 12, 18)
```

In your timezone:
- **UTC+0**: 00:00, 06:00, 12:00, 18:00
- **UTC-5 (EST)**: 19:00, 01:00, 07:00, 13:00
- **UTC+1 (CET)**: 01:00, 07:00, 13:00, 19:00

### Manual Triggers

You can manually run the workflow anytime:

1. Go to your repository → **Actions**
2. Click "Spotify Discovery Engine"
3. Click "Run workflow"
4. Wait for it to complete

### Workflow Steps

Each workflow execution:

1. ✅ Checks out your repository
2. ✅ Sets up Python 3.11
3. ✅ Installs UV package manager
4. ✅ Installs dependencies (spotipy, python-dotenv)
5. ✅ Runs `uv run python main.py`
6. ✅ Updates your Discovery Engine playlist
7. ✅ Logs statistics and completion

### Authentication Flow

1. GitHub Actions reads `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` from Secrets
2. Code detects `CI` environment variable (set by GitHub Actions)
3. Uses cached token from `.cache` file
4. No browser needed (headless execution)
5. Playlist automatically updates

## Monitoring

### View Logs

1. Go to **Actions** tab
2. Click the latest workflow run
3. Click "discovery" job
4. Scroll through console output to see:
   - Authentication status
   - Recently played tracks loaded
   - Tracks generated and filtered
   - Playlist updated
   - Statistics logged

### Common Log Messages

```
INFO - Step 1: Authenticating with Spotify...
✓ Authentication successful

INFO - Step 3: Fetching recently played tracks...
✓ Recently played tracks stored

INFO - Step 5: Generating random candidate tracks...
✓ Generated 28 unplayed candidate tracks

INFO - Step 7: Updating playlist with new tracks...
✓ Added 28 new tracks to playlist
```

### Troubleshooting Workflow Failures

**"Authentication failed"**
- Verify secrets are set correctly in Settings → Secrets
- Ensure `.cache` file is committed and on GitHub

**"Playlist not found"**
- The first run creates the playlist
- Subsequent runs update it
- Check your Spotify account for "Discovery Engine" playlist

**"Rate limited (429)"**
- Built-in retry logic handles this
- Delays automatically increase
- Usually resolves on next run

**"Token expired"**
- Regenerate locally: `uv run main.py`
- Commit updated `.cache`
- Push to GitHub

## Configuration

### Change Schedule

To run more or less frequently, edit `.github/workflows/discovery.yml`:

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # Change this line
```

Examples:
- `0 */3 * * *` - Every 3 hours
- `0 9 * * *` - Once daily at 9 AM UTC
- `0 */12 * * *` - Every 12 hours

### Disable Workflow

To temporarily disable the workflow:

1. Go to **Actions**
2. Click "Spotify Discovery Engine"
3. Click **...** menu
4. Select "Disable workflow"

To re-enable:
1. Click "Enable workflow"

### Delete Workflow

To remove GitHub Actions automation:

1. Delete `.github/workflows/discovery.yml`
2. Commit and push
3. Workflow will no longer run

## Security Considerations

### OAuth Token (`.cache` file)

- Contains your Spotify refresh token
- Only useful with your Client Secret
- If leaked, someone could update your playlists
- Safe to commit if you trust the repository

### GitHub Secrets

- Never visible in logs
- Encrypted at rest on GitHub
- Only available to workflow runs
- Safe practice

### Recommendation

- Keep your GitHub repository **private** if using this approach
- Or, regenerate credentials if accidentally exposed
- Consider creating a separate Spotify app for automation

## Advanced Usage

### Conditional Workflow Runs

Modify `.github/workflows/discovery.yml` to run only on certain conditions:

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'
    # Run only on weekdays (0 = Sunday, 1 = Monday)
  pull_request:
    # Also run when PRs are created
```

### Custom Environment Variables

Add to workflow `env` section:

```yaml
env:
  SPOTIPY_CLIENT_ID: ${{ secrets.SPOTIPY_CLIENT_ID }}
  SPOTIPY_CLIENT_SECRET: ${{ secrets.SPOTIPY_CLIENT_SECRET }}
  SPOTIPY_REDIRECT_URI: ${{ secrets.SPOTIPY_REDIRECT_URI }}
  CUSTOM_VAR: "value"
```

### Notifications

GitHub can notify you of workflow failures. Set in **Settings → Actions → General**.

## FAQ

**Q: Does this cost money?**
A: No. GitHub Actions includes 2,000 free minutes per month. This workflow takes ~2 minutes per run, so 300 free runs per month.

**Q: Can I run it more frequently?**
A: Yes. Change the cron schedule in `.github/workflows/discovery.yml`. More frequent = more API calls, but still well within Spotify rate limits.

**Q: What if I change my Spotify password?**
A: Your cached token remains valid. No action needed.

**Q: What if I revoke the app's permission?**
A: Workflow will fail with authentication error. Regenerate locally (`uv run main.py`) and commit the new `.cache`.

**Q: Can I see the playlist being updated in real-time?**
A: No, but you can check your Spotify app every 6 hours or manually trigger the workflow.

**Q: What if the discovery engine crashes during the workflow?**
A: GitHub logs the error. Check the Actions tab for details. Fix locally and push the fix.

## Disabling GitHub Actions

To go back to local-only operation:

```bash
# Delete the workflow file
rm .github/workflows/discovery.yml

# Or just disable it
# Settings → Actions → General → (disable)
```

The discovery engine will continue to work locally with `uv run main.py`.

## Next Steps

1. ✅ Run `uv run main.py` locally (generates `.cache`)
2. ✅ Commit `.cache` to GitHub
3. ✅ Add Secrets in GitHub Settings
4. ✅ Watch first automatic run in Actions tab
5. ✅ Check your Spotify app for new tracks every 6 hours

---

**Questions?** See `README.md` for general documentation or check GitHub Actions logs for specific errors.
