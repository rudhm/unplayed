# CI/CD Authentication Cleanup Guide

## Problem: "Works Locally But Fails in CI"

This happens when local `.cache` and CI `SPOTIFY_CACHE_JSON` have different scopes.

---

## One-Time Cleanup (Do This Now)

### Step 1: Clean Local Auth
```bash
# Delete old token
rm .cache

# Regenerate with updated scopes
python main.py
# Browser opens → Authorize → See "Read your top artists"

# Verify new scopes
cat .cache | python3 -c "import sys, json; print(json.load(sys.stdin).get('scope', ''))" | grep user-top-read
# Should see "user-top-read" in output
```

### Step 2: Update CI Secret
```bash
# Copy the new token
cat .cache

# Manual steps:
# 1. GitHub → Settings → Secrets and variables → Actions
# 2. Find: SPOTIFY_CACHE_JSON
# 3. Click: Update (or Delete + Create new)
# 4. Paste: ENTIRE JSON output (starts with {, ends with })
# 5. Save

# Verify length (optional)
cat .cache | wc -c
# Note the byte count - useful for troubleshooting
```

### Step 3: Verify Consistency
```bash
# Local scopes
cat .cache | python3 -c "import sys, json; print('Local scopes:', json.load(sys.stdin).get('scope', ''))"

# CI scopes (after updating secret)
# Trigger a workflow run manually
# Check workflow logs for: "Scopes:" or "Authentication successful"
```

---

## Verification Checklist

✅ Local `.cache` file has `user-top-read` scope
✅ GitHub Secret `SPOTIFY_CACHE_JSON` updated with new token
✅ Local test passes: `python3 test_top_artists.py`
✅ CI workflow runs successfully
✅ Both local and CI see same scopes in logs

---

## Troubleshooting

### CI Still Fails After Updating Secret

**Check 1: Secret Was Actually Updated**
```bash
# In GitHub Actions workflow logs, look for:
DEBUG - Loaded Spotify token from SPOTIFY_CACHE_JSON

# If you see "No Spotify OAuth token found" → secret not loaded
# If you see "Failed to decode" → JSON format issue
```

**Check 2: Token Regeneration**
```bash
# Make sure you regenerated AFTER adding user-top-read scope
# Check git log:
git log --oneline -5
# Should see commit with scope change BEFORE you regenerated token
```

**Check 3: Scope Mismatch**
```python
# Add temporary debug to spotify_client.py (line 111):
logger.info(f"Requested scopes: {' '.join(scope)}")

# Then check CI logs - should show user-top-read
```

### "Invalid Grant" Error in CI

**Cause:** Token expired or revoked

**Fix:**
```bash
# Regenerate locally
rm .cache
python main.py

# Update GitHub Secret immediately
cat .cache  # Copy to SPOTIFY_CACHE_JSON
```

### Local Works, CI Gets 403

**Diagnosis:**
- Local has new token with `user-top-read`
- CI has old token without `user-top-read`

**Fix:** Update GitHub Secret (Step 2 above)

---

## Preventing Future Issues

### 1. Document Required Scopes
In your `.env.example` or README, list:
```
Required OAuth Scopes:
- user-read-recently-played
- playlist-modify-private  
- playlist-modify-public
- user-library-read
- user-top-read (Premium only)
```

### 2. Add Scope Validation
Optional enhancement to `spotify_client.py`:
```python
def validate_token_scopes(token_info, required_scopes):
    """Validate token has all required scopes."""
    token_scopes = token_info.get('scope', '').split()
    missing = [s for s in required_scopes if s not in token_scopes]
    if missing:
        logger.warning(f"Missing scopes: {missing}")
        return False
    return True
```

### 3. Token Expiry Reminders
Spotify refresh tokens can expire after ~6 months of inactivity.

**Best Practice:** Regenerate tokens:
- When adding new scopes
- Every 6 months (preventive)
- After any "invalid_grant" errors

---

## Quick Reference Commands

```bash
# Check local scopes
cat .cache | python3 -c "import sys, json; print(json.load(sys.stdin).get('scope', ''))"

# Regenerate token
rm .cache && python main.py

# Copy token for CI
cat .cache

# Test locally
python3 test_top_artists.py

# Test full app
python main.py

# Check CI logs
gh run list --limit 5  # If gh CLI installed
```

---

## Success Criteria

After cleanup, you should see:

**Local:**
```
INFO - Building taste profile: fetching top artists...
DEBUG - [API CALL] current_user_top_artists
DEBUG - [API SUCCESS] current_user_top_artists
INFO - ✓ Loaded 20 artists from top artists
```

**CI (GitHub Actions):**
```
INFO - Building taste profile: fetching top artists...
DEBUG - [API CALL] current_user_top_artists
DEBUG - [API SUCCESS] current_user_top_artists  # For Premium
OR
INFO - Skipping top artists (requires Spotify Premium...)  # For Free
```

Both should complete successfully and update playlist.

---

## When to Regenerate Tokens

| Scenario | Action |
|----------|--------|
| Adding new scope | ✅ Regenerate + update CI |
| Changing existing scope | ✅ Regenerate + update CI |
| Token expired (>6 months) | ✅ Regenerate + update CI |
| "Invalid grant" error | ✅ Regenerate + update CI |
| Moving to new Spotify app | ✅ Regenerate + update CI |
| Switching accounts | ✅ Regenerate + update CI |
| Code changes only | ❌ No regeneration needed |

---

## Final Verification

Run this complete check:
```bash
# 1. Local cleanup
rm .cache
python main.py

# 2. Local test
python3 test_top_artists.py

# 3. Full run
python main.py

# 4. Update CI
cat .cache  # Copy to GitHub Secret

# 5. Manual CI trigger
# GitHub → Actions → Run workflow

# 6. Check CI logs
# Should see "[API SUCCESS]" or graceful skip messages
```

All ✅? You're done! 🎉
