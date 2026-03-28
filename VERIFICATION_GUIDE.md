# Verification and Testing Guide

## CRITICAL: Test Before Assuming It's Fixed

This guide walks through verifying the Premium API fix actually works.

---

## Step 1: Check Current Token Scopes

Before regenerating, see what scopes your current token has:

```bash
# Check if .cache exists
ls -la .cache

# View token scopes (if .cache exists)
cat .cache | python3 -c "import sys, json; data=json.load(sys.stdin); print('Scopes:', data.get('scope', 'NO SCOPE'))"
```

**Expected Output:**
- If `user-top-read` is present → Good, scope is there
- If `user-top-read` is missing → You MUST regenerate token

---

## Step 2: Regenerate Token (If Needed)

If `user-top-read` was missing from Step 1:

```bash
# Delete old token
rm .cache

# Run script to generate new token
python main.py
```

**What should happen:**
1. Browser opens to Spotify authorization page
2. Shows list of permissions including "Read your top artists"
3. Click "Agree"
4. Terminal shows "Authentication successful"

**Verify new token:**
```bash
cat .cache | python3 -c "import sys, json; data=json.load(sys.stdin); print('Scopes:', data.get('scope', 'NO SCOPE'))" | grep user-top-read
```

Should see `user-top-read` in the output.

---

## Step 3: Run Test Script

Use the dedicated test script to verify the top artists endpoint:

```bash
python3 test_top_artists.py
```

### Possible Outcomes:

#### ✅ SUCCESS (Premium User)
```
======================================================================
TESTING: current_user_top_artists()
======================================================================

[1/3] Authenticating with Spotify...
✓ Authentication successful

[2/3] Fetching user info to check account type...
✓ Account type: premium
  User: YourName
  Email: you@email.com

[3/3] Calling current_user_top_artists(limit=5)...
✓ SUCCESS! Top artists fetched successfully
  Total items: 50
  Items returned: 5

  Top 5 Artists:
    1. Artist Name 1
    2. Artist Name 2
    3. Artist Name 3
    4. Artist Name 4
    5. Artist Name 5

======================================================================
✅ TEST PASSED - No Premium restriction detected
======================================================================
```

**What this means:** The fix works! You can use the top artists endpoint.

---

#### ⚠️ EXPECTED FAILURE (Free User)
```
======================================================================
TESTING: current_user_top_artists()
======================================================================

[1/3] Authenticating with Spotify...
✓ Authentication successful

[2/3] Fetching user info to check account type...
✓ Account type: free
  User: YourName
  Email: you@email.com

[3/3] Calling current_user_top_artists(limit=5)...

❌ ERROR: 403 Forbidden: Premium subscription required

Diagnostics:
----------------------------------------------------------------------
⚠️  HTTP 403 Forbidden detected

🔴 ROOT CAUSE: Premium Subscription Required
   Your Spotify account needs a Premium subscription
   to access the top artists endpoint.

   This is expected for free tier users.
   The main app will gracefully skip this data source.
======================================================================
```

**What this means:** You have a free account. This is EXPECTED. The main app will gracefully skip this data source and use the other 3 sources (followed artists, liked songs, playlists).

---

#### ❌ BAD FAILURE (Missing Scope)
```
❌ ERROR: 403 Forbidden

Diagnostics:
----------------------------------------------------------------------
⚠️  HTTP 403 Forbidden detected

🔴 ROOT CAUSE: Missing OAuth Scope
   The 'user-top-read' scope may not be in your token.

   FIX: Regenerate your token:
   1. rm .cache
   2. python main.py
   3. Reauthorize in browser
======================================================================
```

**What this means:** Your token doesn't have the `user-top-read` scope. Follow the fix steps and try again.

---

## Step 4: Run Full Application

After verifying the test passes (or fails expectedly for free users):

```bash
python main.py
```

### Watch for these log messages:

**For Premium Users:**
```
INFO - Building taste profile: fetching top artists...
DEBUG - [API CALL] current_user_top_artists
DEBUG - [API SUCCESS] current_user_top_artists
INFO - ✓ Loaded 20 artists from top artists
INFO - Building taste profile: fetching followed artists...
```

**For Free Users:**
```
INFO - Building taste profile: fetching top artists...
DEBUG - [API CALL] current_user_top_artists
ERROR - [API ERROR] current_user_top_artists: 403 Forbidden...
INFO - [API DIAGNOSIS] current_user_top_artists: Premium subscription required (expected for free users)
INFO - Skipping top artists (requires Spotify Premium subscription - continuing with other sources)
INFO - Building taste profile: fetching followed artists...
DEBUG - [API CALL] current_user_followed_artists
DEBUG - [API SUCCESS] current_user_followed_artists
```

**Both users should see:**
```
INFO - ✓ Added N new tracks to playlist
INFO - DISCOVERY ENGINE COMPLETE
```

---

## Step 5: Enable Debug Logging (Optional)

For even more detailed diagnostics:

```bash
# Enable debug level logging
export LOG_LEVEL=DEBUG
python main.py
```

This shows every API call:
```
DEBUG - [API CALL] current_user_top_artists
DEBUG - [API SUCCESS] current_user_top_artists
DEBUG - [API CALL] current_user_followed_artists
DEBUG - [API SUCCESS] current_user_followed_artists
DEBUG - [API CALL] current_user_saved_tracks
DEBUG - [API SUCCESS] current_user_saved_tracks
```

If an API call fails, you'll see:
```
ERROR - [API ERROR] <endpoint_name>: <error_message>
INFO/WARNING - [API DIAGNOSIS] <endpoint_name>: <diagnosis>
```

---

## Step 6: Update CI/CD Token

If you regenerated the token locally and the test passes:

```bash
# Copy the new token
cat .cache

# Then:
# 1. Go to GitHub: Settings → Secrets and variables → Actions
# 2. Find: SPOTIFY_CACHE_JSON
# 3. Click: Update
# 4. Paste: The ENTIRE output (starts with {, ends with })
# 5. Save

# Verify it copied correctly (check length)
cat .cache | wc -c
# Remember this number, compare with GitHub Secret length
```

---

## Common Issues and Fixes

### Issue: "403 Forbidden" Even After Regenerating Token

**Diagnosis:**
```bash
# Check scopes in token
cat .cache | python3 -c "import sys, json; print(json.load(sys.stdin).get('scope', ''))" | grep user-top-read
```

If `user-top-read` is missing:
1. Check `spotify_client.py` line 87 has `"user-top-read",`
2. Delete `.cache` again
3. Run `python main.py` again
4. Look for "user-top-read" in the browser authorization screen

### Issue: "Invalid Scope" Error

**Cause:** Typo in scope name

**Fix:**
```bash
# Check line 87 in spotify_client.py
grep -n "user-top-read" spotify_client.py

# Should see line 87 with exactly: "user-top-read",
```

### Issue: Test Passes Locally But Fails in CI

**Cause:** GitHub Secret has old token

**Fix:**
```bash
# Generate fresh token locally
rm .cache
python main.py

# Update GitHub Secret
cat .cache  # Copy entire output
# Paste into SPOTIFY_CACHE_JSON secret

# Trigger workflow manually to test
# GitHub Actions → Run workflow
```

---

## Success Criteria

✅ **Test script runs without errors** (or expected Premium error for free users)
✅ **Main app completes successfully**
✅ **Playlist gets updated with new tracks**
✅ **Logs show appropriate messages for account type**
✅ **CI/CD workflow completes successfully** (if using GitHub Actions)

---

## Quick Debug Commands

```bash
# 1. Check if token file exists
ls -la .cache

# 2. View token scopes
cat .cache | python3 -c "import sys, json; print(json.load(sys.stdin).get('scope', 'NO SCOPE'))"

# 3. Test top artists endpoint
python3 test_top_artists.py

# 4. Run full app
python main.py

# 5. Check logs with debug enabled
LOG_LEVEL=DEBUG python main.py

# 6. Verify syntax
python3 -m py_compile discovery.py spotify_client.py

# 7. Check GitHub Actions logs
gh run list --limit 5  # If gh CLI installed
```

---

## Next Steps After Verification

Once everything works:

1. ✅ Commit changes to git
2. ✅ Update GitHub Secret (if using CI/CD)
3. ✅ Document in README any account-specific behavior
4. ✅ Monitor first few automated runs

**The fix is complete when:**
- Local testing succeeds
- CI/CD runs succeed (if applicable)
- Users understand Premium vs Free behavior
- Logs clearly indicate what's happening
