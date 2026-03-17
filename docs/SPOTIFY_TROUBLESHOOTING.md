# Spotify CI/CD Troubleshooting Guide

This guide helps you diagnose and fix common issues with Spotify OAuth authentication in GitHub Actions.

## Error: "Failed to decode SPOTIFY_CACHE_JSON"

### What This Means
The `SPOTIFY_CACHE_JSON` secret contains something that isn't valid JSON. Common causes:
- Extra whitespace or newlines around the JSON
- Quotes wrapped around the JSON string
- Incomplete JSON (missing fields)
- Wrong secret value pasted

### How to Fix

#### Option 1: Verify Your Local .cache File

First, ensure your local `.cache` file is valid JSON:

```bash
# Validate the .cache file locally
python -c "import json; token = json.load(open('.cache')); print('✓ Valid JSON'); print('Token fields:', list(token.keys()))"
```

Expected output:
```
✓ Valid JSON
Token fields: ['access_token', 'token_type', 'expires_in', 'refresh_token', 'scope', 'expires_at']
```

If this fails, regenerate the token:
```bash
rm .cache
python main.py
```

#### Option 2: Verify the GitHub Secret

1. Go to your repository: **Settings** → **Secrets and variables** → **Actions**
2. Find `SPOTIFY_CACHE_JSON`
3. Click the pencil icon to edit it
4. Verify the value:
   - ✅ Starts with `{` (opening brace)
   - ✅ Ends with `}` (closing brace)
   - ✅ No surrounding quotes
   - ✅ Looks like: `{"access_token": "BQD...", ...}`

If it looks wrong, delete it and recreate:

```bash
# On your local machine, export the token
cat .cache
```

Then:
1. Copy the entire output (including `{` and `}`)
2. In GitHub Secrets UI, delete the old `SPOTIFY_CACHE_JSON`
3. Create a new secret with:
   - Name: `SPOTIFY_CACHE_JSON`
   - Value: **Paste the entire output from `cat .cache`**
4. Click "Add secret"

#### Option 3: Debug in the Workflow

Add a debug step to see what's being passed:

```yaml
- name: Debug Spotify Secret
  run: |
    echo "Secret length: ${#SPOTIFY_CACHE_JSON}"
    echo "First 100 chars: ${SPOTIFY_CACHE_JSON:0:100}"
    python -c "import os, json; val = os.getenv('SPOTIFY_CACHE_JSON', ''); print('Value:', repr(val[:100]))"
  env:
    SPOTIFY_CACHE_JSON: ${{ secrets.SPOTIFY_CACHE_JSON }}
```

This shows:
- Length of the secret value
- First 100 characters (sanitized)
- Whether it has leading/trailing whitespace

---

## Error: "No Spotify OAuth token found in CI environment"

This means `SPOTIFY_CACHE_JSON` is either:
- Not set in GitHub Secrets
- Empty
- All whitespace

### How to Fix

1. **Check the secret exists:**
   - Go to Settings → Secrets and variables → Actions
   - Look for `SPOTIFY_CACHE_JSON`
   - If missing, create it with the token from `cat .cache`

2. **Verify it's not empty:**
   ```bash
   # Locally, check your .cache file exists and has content
   cat .cache | wc -c
   ```
   Should show a number > 100 (typical tokens are 500+ bytes)

3. **Regenerate if corrupted:**
   ```bash
   rm .cache
   python main.py
   cat .cache  # Copy this output to GitHub Secrets
   ```

---

## Error: "invalid_grant" or "token expired"

This means the refresh token is no longer valid.

### How to Fix

1. **Regenerate locally:**
   ```bash
   rm .cache
   python main.py
   ```
   You'll be prompted to authorize in your browser.

2. **Export and update the secret:**
   ```bash
   cat .cache  # Copy this
   ```

3. **Update GitHub Secret:**
   - Settings → Secrets → Edit `SPOTIFY_CACHE_JSON`
   - Replace with new token from `cat .cache`
   - Save

4. **Test the workflow:**
   - Go to Actions → Unplayed Discovery Engine
   - Click "Run workflow"

---

## Error: "Missing Spotify credentials"

This means `SPOTIPY_CLIENT_ID` or `SPOTIPY_CLIENT_SECRET` are not set.

### How to Fix

1. **Verify the secrets exist:**
   - Settings → Secrets and variables → Actions
   - Check for `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET`

2. **Get credentials from Spotify:**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Find your application
   - Copy the Client ID and Client Secret

3. **Create the secrets:**
   - Name: `SPOTIPY_CLIENT_ID` → Value: Your Client ID
   - Name: `SPOTIPY_CLIENT_SECRET` → Value: Your Client Secret
   - Name: `SPOTIPY_REDIRECT_URI` → Value: `http://127.0.0.1:8888/callback`

---

## Local Development Issues

### "No module named 'spotipy'"

Install dependencies:
```bash
pip install spotipy python-dotenv
```

### "No cached token found locally"

Run the script to generate the token:
```bash
python main.py
```

You'll be prompted to authorize in your browser. This creates the `.cache` file.

### ".env file not found"

Create it from the example:
```bash
cp .env.example .env
```

Then edit `.env` with your Spotify credentials:
```
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

---

## Workflow Debugging

### Run Workflow with Debug Logging

1. Add this to your workflow YAML:
   ```yaml
   - name: Run discovery engine
     run: python main.py
     env:
       # ... other vars
       SPOTIFY_CACHE_JSON: ${{ secrets.SPOTIFY_CACHE_JSON }}
   ```

2. Check the workflow logs:
   - Go to Actions → Unplayed Discovery Engine
   - Click the failed run
   - Expand "Run discovery engine"
   - Look for error messages

### Common Log Patterns

**Pattern: "Failed to decode SPOTIFY_CACHE_JSON"**
```
WARNING:spotify_client:Failed to decode SPOTIFY_CACHE_JSON: Expecting value: line 1 column 1
ERROR:__main__:Pipeline failed: No Spotify OAuth token found in CI environment
```
→ See "Error: Failed to decode SPOTIFY_CACHE_JSON" section above

**Pattern: "no such file or directory: '.cache'"**
```
FileNotFoundError: [Errno 2] No such file or directory: '.cache'
```
→ Token not found. Make sure `SPOTIFY_CACHE_JSON` secret is set.

**Pattern: "Couldn't decode JSON from cache"**
```
WARNING:spotipy.cache_handler:Couldn't decode JSON from cache at: <path>
```
→ Same as "Failed to decode" - the secret JSON is malformed.

---

## Security Checklist

- ✅ Never commit `.cache` file to repository
- ✅ Never commit `.env` file to repository
- ✅ Use GitHub Secrets for sensitive data
- ✅ Rotate tokens if compromised
- ✅ Keep `.cache` and `.env` in `.gitignore`
- ✅ Review GitHub Actions logs don't expose secrets

---

## Getting Help

If you're still stuck:

1. **Verify local setup works:**
   ```bash
   python main.py
   ```
   Ensure this completes successfully and adds tracks to your playlist.

2. **Test the .cache file:**
   ```bash
   python -c "import json; json.load(open('.cache'))"
   ```
   Should print nothing (success) or JSON error.

3. **Check GitHub Secret:**
   - Go to Settings → Secrets
   - Edit `SPOTIFY_CACHE_JSON`
   - Verify format is correct (see examples above)

4. **Enable workflow debug:**
   Add these at the start of your workflow:
   ```yaml
   env:
     ACTIONS_STEP_DEBUG: true
   ```
   This shows more detailed logs.

5. **Regenerate everything:**
   ```bash
   # Local
   rm .cache
   python main.py
   cat .cache
   
   # GitHub: Delete and recreate all secrets
   # Then run workflow again
   ```

---

## References

- [GitHub Secrets Docs](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- [Spotipy OAuth Docs](https://spotipy.readthedocs.io/en/latest/#client-credentials-flow)
- [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
