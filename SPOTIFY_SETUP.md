# Spotify OAuth Setup for CI/CD

This guide explains how to securely configure Spotify OAuth authentication for GitHub Actions CI/CD pipelines.

## Overview

The Discovery Engine uses Spotify OAuth to authenticate and access your music data. In local environments, the authenticated token is cached in `.cache` file. For CI/CD environments (like GitHub Actions), we securely pass this token via GitHub Secrets.

## Security Best Practices

✅ **DO:**
- Store tokens as GitHub Secrets (encrypted at rest)
- Rotate tokens periodically
- Use environment variables to pass secrets
- Include `.cache` and `.env` in `.gitignore`

❌ **DON'T:**
- Commit `.cache` files to the repository
- Commit `.env` files to the repository
- Hardcode tokens in workflow files
- Use personal access tokens for production

## Step 1: Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create or select your application
3. Note your **Client ID** and **Client Secret**
4. Set Redirect URI to: `http://127.0.0.1:8888/callback`

## Step 2: Generate OAuth Token Locally

Run the script locally once to generate and cache the OAuth token:

```bash
# Set up local environment
cp .env.example .env

# Edit .env with your Spotify credentials
# SPOTIPY_CLIENT_ID=your_client_id
# SPOTIPY_CLIENT_SECRET=your_client_secret
# SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Run the script (you'll be prompted to authorize in a browser)
python main.py
```

This creates a `.cache` file containing your OAuth token. **Keep this file private—never commit it.**

## Step 3: Export Token for GitHub Secrets

Convert the `.cache` file to a JSON string for secure storage:

```bash
# Display the cache file as a JSON string (ready to copy)
cat .cache
```

The output will be a JSON object like:
```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "...",
  "expires_at": 1234567890.123456
}
```

## Step 4: Store Credentials as GitHub Secrets

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**
2. Create the following secrets:

   | Secret Name | Value | Source |
   |---|---|---|
   | `SPOTIPY_CLIENT_ID` | Your Spotify Client ID | Spotify Dashboard |
   | `SPOTIPY_CLIENT_SECRET` | Your Spotify Client Secret | Spotify Dashboard |
   | `SPOTIPY_REDIRECT_URI` | `http://127.0.0.1:8888/callback` | Fixed value |
   | `SPOTIFY_CACHE_JSON` | Your `.cache` file contents | See instructions below |

### Storing SPOTIFY_CACHE_JSON Correctly

⚠️ **Common mistake:** Extra whitespace or incomplete copying causes JSON decode errors.

**Follow these steps exactly:**

1. **Export your token** (from Step 2):
   ```bash
   cat .cache
   ```
   Output will look like:
   ```json
   {"access_token": "...", "token_type": "Bearer", "expires_in": 3600, ...}
   ```

2. **In GitHub UI:**
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `SPOTIFY_CACHE_JSON`
   - Value: **Paste the ENTIRE JSON output from `cat .cache`**
     - Start with the opening `{`
     - End with the closing `}`
     - Don't add quotes around it
     - Include all fields (access_token, refresh_token, expires_in, expires_at, etc.)

3. **Verify the paste:**
   - ✅ Starts with `{` (opening brace)
   - ✅ Ends with `}` (closing brace)
   - ✅ No extra quotes around the JSON
   - ✅ No truncation (full content pasted)
   - ❌ NOT wrapped in quotes like `"{ ... }"`
   - ❌ NOT multiple lines with just the token value

4. **Click "Add secret"**

**Example - CORRECT Format:**
```
{"access_token": "BQD...", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "AQA...", "scope": "...", "expires_at": 1234567890.123456}
```

**Example - WRONG Format (common errors):**
```
"{"access_token": "BQD...", ...}"    ← Extra quotes
{ ... }                              ← With newlines/whitespace
'{ ... }'                            ← Single quotes
BQD...                               ← Only the token, missing JSON structure
{"access_token": "BQD..."}           ← Incomplete JSON (missing other fields)
```

### Troubleshooting SPOTIFY_CACHE_JSON

If you get `Failed to decode SPOTIFY_CACHE_JSON`:

1. **Check the secret value in GitHub:**
   - Settings → Secrets → Click the pencil icon next to `SPOTIFY_CACHE_JSON`
   - Verify it starts with `{` and ends with `}`
   - If not, delete and recreate it

2. **Re-export and re-paste:**
   ```bash
   # Local machine
   cat .cache
   # Copy the output
   # Go to GitHub UI and update the secret
   ```

3. **Verify the .cache file locally:**
   ```bash
   python -c "import json; json.load(open('.cache'))" && echo "✓ Valid JSON"
   ```
   This confirms your `.cache` file is valid JSON.

4. **Run the workflow again:**
   - After updating the secret, go to Actions → Unplayed Discovery Engine → Run workflow

## Step 5: Verify the Setup

1. Run the workflow manually: **Actions** → **Unplayed Discovery Engine** → **Run workflow**
2. Check the logs to ensure the "Run discovery engine" step completes successfully
3. If it fails, verify all secrets are set correctly

## Token Refresh

Spotify OAuth tokens expire after ~1 hour. The Spotipy library automatically refreshes tokens using the `refresh_token` stored in your cache.

### When to Update the Cached Token

Update `SPOTIFY_CACHE_JSON` in GitHub Secrets if:
- You see `"expired": true` in workflow logs
- Workflow fails with "invalid_grant" errors
- More than 6 months have passed since initial setup

To refresh:
1. Run `python main.py` locally
2. Copy the new `.cache` contents: `cat .cache`
3. Update the `SPOTIFY_CACHE_JSON` secret in GitHub

## Troubleshooting

### "No Spotify OAuth token found in CI environment"
- Verify `SPOTIFY_CACHE_JSON` secret is set correctly
- Check the secret contains valid JSON (no extra quotes around it)
- Ensure the JSON is properly formatted

### "Couldn't decode JSON from cache"
- Verify you copied the entire `.cache` file contents
- Check for extra newlines or special characters
- Make sure the JSON is a single continuous string

### "invalid_grant" or "token expired"
- The refresh token is invalid or expired
- Follow "When to Update the Cached Token" section above

### Workflow runs but doesn't add tracks to playlist
- Check that your Spotify account and scopes are correct
- Verify the playlist exists in your Spotify account
- Review the full workflow logs for additional errors

## Local Development

For local development, create a `.env` file (never commit this):

```bash
# .env (add to .gitignore)
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

The script will use the cached `.cache` file for subsequent runs.

## Security Notes

- GitHub Secrets are encrypted at rest and in transit
- Workflow logs don't display secret values
- Secrets are only available to authenticated workflows on your repository
- Consider rotating your Spotify API credentials periodically

For more information, see:
- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- [Spotipy Documentation](https://spotipy.readthedocs.io/)
