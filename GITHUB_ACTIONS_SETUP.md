# GitHub Actions Setup Guide - Weekly Automated Discovery

This guide will help you set up **automatic weekly music discovery** using GitHub Actions, completely free! Your Unplayed playlist will update every Monday without you lifting a finger.

## 📋 Prerequisites

Before starting, make sure you have:

✅ A GitHub account with your Unplayed repository
✅ All API keys working locally (test with `python main.py`)
✅ Make.com webhook configured (see `MAKE_WEBHOOK_SETUP.md`)
✅ Basic understanding of environment variables

## 🚀 Setup Steps

### Step 1: Verify Workflow File Exists

The workflow file has already been created at:
```
.github/workflows/discovery_cron.yml
```

This file tells GitHub Actions:
- **When to run:** Every Monday at 00:00 UTC
- **What to run:** Your `main.py` script
- **How to run:** Using `uv` with your dependencies

### Step 2: Add Secrets to GitHub

**IMPORTANT:** Never commit your `.env` file or API keys to GitHub!

Instead, we'll store them securely in GitHub Secrets:

1. **Go to your repository on GitHub.com**

2. **Navigate to Settings**
   - Click the **Settings** tab (top right)
   - Click **Secrets and variables** in the left sidebar
   - Click **Actions**

3. **Add each secret** (click "New repository secret" for each):

#### Required Secrets

| Secret Name | Value | Where to Get It |
|-------------|-------|----------------|
| `LASTFM_API_KEY` | Your Last.fm API key | https://www.last.fm/api/account/create |
| `LASTFM_USERNAME` | Your Last.fm username | Your Last.fm profile |
| `MAKE_WEBHOOK_URL` | Your Make.com webhook URL | Make.com scenario (see MAKE_WEBHOOK_SETUP.md) |
| `SPOTIPY_CLIENT_ID` | Your Spotify app client ID | https://developer.spotify.com/dashboard |
| `SPOTIPY_CLIENT_SECRET` | Your Spotify app client secret | https://developer.spotify.com/dashboard |
| `SPOTIFY_CACHE_JSON` | Your Spotify auth token (JSON) | See section below ⬇️ |

#### Optional Secrets

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `SPOTIPY_REDIRECT_URI` | Usually `http://127.0.0.1:8888/callback` | Only if you changed it |
| `SPOTIFY_EXPORT_PATH` | Path to your GDPR exports | For better filtering (usually not needed in CI) |
| `IFTTT_WEBHOOK_KEY` | Your IFTTT webhook key | Legacy fallback (optional) |

### Step 3: Get Your Spotify Auth Token (SPOTIFY_CACHE_JSON)

This is the trickiest part! GitHub Actions can't open a browser, so we need to pre-authenticate:

#### Option A: Extract from Local Cache (Easiest)

1. **Run your script locally first:**
   ```bash
   python main.py
   ```

2. **Find the cache file:**
   ```bash
   # Look for .cache or .cache-{username}
   ls -la ~/.cache/spotify/
   # OR in your project directory
   ls -la .cache*
   ```

3. **Copy the entire JSON content:**
   ```bash
   cat ~/.cache/spotify/.cache-YOUR_USERNAME
   # OR
   cat .cache
   ```

4. **Add to GitHub Secrets:**
   - Name: `SPOTIFY_CACHE_JSON`
   - Value: The entire JSON content (including `{}` brackets)

#### Option B: Use the Verification Script

```bash
# Run this to see your token
python verify_auth.py

# If it shows a valid token, extract it:
cat .cache
```

#### Example SPOTIFY_CACHE_JSON Format:

```json
{
  "access_token": "BQC9K...(long string)...7nX",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "AQD...(long string)...kz",
  "scope": "playlist-read-private playlist-modify-private playlist-modify-public",
  "expires_at": 1234567890
}
```

**Note:** The `refresh_token` is the important part - it lets GitHub Actions get new access tokens automatically!

### Step 4: Test the Workflow

Don't wait until Monday! Test it now:

1. **Go to the Actions tab** on GitHub.com

2. **Select "Weekly Music Discovery"** from the left sidebar

3. **Click "Run workflow"** dropdown button (right side)

4. **Click the green "Run workflow" button**

5. **Watch the logs:**
   - Click on the running job
   - Expand each step to see real-time logs
   - Look for Phase 1-4 output from your script

6. **Check for success:**
   - ✅ Green checkmark = Success! Check your Spotify playlist!
   - ❌ Red X = Something failed (see Troubleshooting below)

### Step 5: Verify Your Playlist

After a successful run:
1. Open Spotify
2. Go to Your Library → Playlists
3. Find "Unplayed Discoveries"
4. You should see 40 new tracks!

## 📅 Schedule Configuration

### Default Schedule

```yaml
cron: '0 0 * * 1'
```

This runs at **00:00 UTC every Monday**.

### Adjust for Your Timezone

GitHub uses **UTC time**. Convert your desired local time:

| Your Time Zone | Desired Run Time | Cron Expression |
|----------------|------------------|-----------------|
| EST (UTC-5) | Monday 8:00 AM | `'0 13 * * 1'` |
| PST (UTC-8) | Monday 8:00 AM | `'0 16 * * 1'` |
| GMT (UTC+0) | Monday 9:00 AM | `'0 9 * * 1'` |
| CET (UTC+1) | Monday 10:00 AM | `'0 9 * * 1'` |

**How to calculate:**
1. Find your UTC offset (e.g., EST = UTC-5)
2. Add the offset to your desired hour (8 AM + 5 = 13:00 UTC)
3. Use the result in the cron expression: `'0 13 * * 1'`

### Run More/Less Frequently

```yaml
# Every day at midnight
cron: '0 0 * * *'

# Twice a week (Monday and Thursday)
cron: '0 0 * * 1,4'

# First day of every month
cron: '0 0 1 * *'

# Every 3 days at 6 PM UTC
cron: '0 18 */3 * *'
```

## 🔧 Troubleshooting

### ❌ "No module named 'requests'" or similar

**Solution:** Make sure your `pyproject.toml` includes all dependencies:
```bash
uv add requests spotipy
```

### ❌ "LASTFM_API_KEY is required"

**Solution:** 
1. Check the secret name is **exactly** `LASTFM_API_KEY` (case-sensitive)
2. Verify the value has no extra spaces
3. Re-run the workflow

### ❌ "Spotify authentication failed"

**Solution:**
1. Verify `SPOTIFY_CACHE_JSON` contains a valid JSON object
2. Make sure it includes the `refresh_token` field
3. Try re-authenticating locally and extracting a fresh token

### ❌ "403 Forbidden" from Spotify

**Solution:**
- This is why we use Make.com webhook!
- Verify `MAKE_WEBHOOK_URL` is set correctly
- Check that your Make.com scenario is **active (ON)**
- Test the webhook with `python test_webhook.py` locally first

### ❌ Workflow doesn't run on schedule

**Solution:**
1. Check if your repository is **public** (private repos need GitHub Actions minutes)
2. Verify the workflow file is in the correct location: `.github/workflows/discovery_cron.yml`
3. Make sure there are no YAML syntax errors (use yamllint or GitHub's editor)

### ❌ "uv: command not found"

**Solution:** The `setup-uv` action should handle this. Try:
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v5
  with:
    version: "latest"
```

### ❌ Workflow runs but no tracks added

**Solution:**
1. Check the logs for error messages
2. Look at Phase 3 output - are tracks being filtered?
3. Verify Make.com webhook is receiving requests
4. Check Make.com scenario execution history

## 📊 Understanding the Workflow Logs

When you view a running workflow, you'll see:

```
✓ Checkout code
✓ Install uv
✓ Set up Python
✓ Run Discovery Script
    Starting Hybrid Discovery Engine (run_id: abc123)
    ============================================================
    PHASE 1: TASTE PROFILE
    ============================================================
    ✓ Fetched 50 top artists from Last.fm
    ...
    ============================================================
    PHASE 4: WEBHOOK EXPORT & PLAYLIST GENERATION
    ============================================================
    → Success: Artist 1 - Track 1
    → Success: Artist 2 - Track 2
    ...
    ✓ Pipeline Complete! Successfully routed 40/40 tracks to Spotify.
✓ Upload output files (if any)
```

## 🎯 Best Practices

### 1. Test Locally First
Always run `python main.py` locally before committing changes.

### 2. Use Webhook Output
Make.com webhook is more reliable than direct Spotify API for automated runs.

### 3. Monitor the First Few Runs
Check the Actions tab after the first scheduled run to catch any issues.

### 4. Keep Secrets Updated
If you regenerate any API keys, update the corresponding GitHub secret.

### 5. Don't Commit Secrets
Never commit `.env` or `.cache` files to GitHub!

## 🔒 Security Notes

✅ **GitHub Secrets are encrypted** - No one can read them (not even you after adding)

✅ **Secrets aren't exposed in logs** - GitHub masks them automatically

✅ **Limited access** - Only the Actions runner can access secrets during runs

❌ **Don't print secrets** - Avoid `echo $LASTFM_API_KEY` in your scripts

❌ **Don't commit tokens** - Add `.env` and `.cache*` to `.gitignore`

## 📈 Usage Limits (Free Tier)

**GitHub Actions:**
- **Public repos:** Unlimited minutes ✅
- **Private repos:** 2,000 minutes/month (enough for ~60 runs)

**Make.com:**
- **Free tier:** 1,000 operations/month
- **40 tracks/week:** ~160 operations/month ✅ Well within limit!

**Last.fm:**
- **Rate limit:** ~5 requests/second
- **Daily limit:** None for standard use ✅

## 🆘 Getting Help

### Check These First:
1. View the workflow logs in the Actions tab
2. Test the script locally: `python main.py`
3. Verify all secrets are set correctly
4. Check Make.com scenario is active

### Common Log Locations:
- Workflow runs: `https://github.com/YOUR_USERNAME/unplayed/actions`
- Spotify Developer Dashboard: `https://developer.spotify.com/dashboard`
- Make.com History: `https://www.make.com/en/scenarios`

## ✅ Verification Checklist

Before going live, verify:

- [ ] Workflow file exists at `.github/workflows/discovery_cron.yml`
- [ ] All required secrets added to GitHub (8 secrets minimum)
- [ ] `SPOTIFY_CACHE_JSON` includes a valid refresh token
- [ ] Make.com webhook scenario is **active (ON)**
- [ ] Test run completed successfully (green checkmark)
- [ ] Spotify playlist updated with tracks
- [ ] `.env` and `.cache*` are in `.gitignore`

## 🎉 Success!

Once everything is working:
1. Your playlist updates automatically every Monday
2. No manual intervention needed
3. Discover new music while you sleep! 🎵

---

## Quick Reference

### Environment Variables Used
```bash
# Required
LASTFM_API_KEY=your_key
LASTFM_USERNAME=your_username
MAKE_WEBHOOK_URL=https://hook.eu1.make.com/YOUR_ID
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIFY_CACHE_JSON={"access_token":"...","refresh_token":"..."}

# Optional
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_EXPORT_PATH=/path/to/exports
IFTTT_WEBHOOK_KEY=your_ifttt_key
```

### Useful Commands
```bash
# Test locally
python main.py

# Test webhook only
python test_webhook.py

# Verify authentication
python verify_auth.py

# Check dependencies
uv pip list
```

### Important Links
- Last.fm API: https://www.last.fm/api/account/create
- Spotify Dashboard: https://developer.spotify.com/dashboard
- Make.com: https://www.make.com
- GitHub Actions Docs: https://docs.github.com/en/actions

---

**Need help?** Create an issue on GitHub or check the other documentation files:
- `MAKE_WEBHOOK_SETUP.md` - Make.com webhook setup
- `README.md` - Main project documentation
- `QUICKSTART.md` - Getting started guide
