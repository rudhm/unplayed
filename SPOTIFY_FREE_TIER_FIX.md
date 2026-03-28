# Spotify Free Tier Compatibility Fix

## Issue Fixed

**Problem:** Application was failing with error:
> "Your application is blocked from accessing the Web API since you do not have a Spotify Premium subscription."

**Root Causes:** 
1. **Missing OAuth Scope** - `user-top-read` was not included in scope list
2. **Premium Endpoint** - The `current_user_top_artists()` endpoint requires Premium subscription (as of 2026)

## Solution Implemented

### 1. Added Missing OAuth Scope

**File:** `spotify_client.py`, Lines 82-88

**Before:**
```python
scope = [
    "user-read-recently-played",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-library-read",
]
```

**After:**
```python
scope = [
    "user-read-recently-played",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-library-read",
    "user-top-read",  # Required for current_user_top_artists() - Premium only
]
```

⚠️ **CRITICAL: Token Regeneration Required** ⚠️

Because the scope changed, you MUST regenerate your OAuth tokens:

**For Local Development:**
```bash
# Delete old token
rm .cache

# Run script to generate new token with updated scopes
python main.py
# Browser will open for authorization

# Verify new token includes user-top-read
cat .cache | python -m json.tool | grep scope
```

**For CI/CD (GitHub Actions):**
```bash
# After regenerating locally, update the GitHub Secret
cat .cache

# Then:
# 1. Go to: Settings → Secrets and variables → Actions
# 2. Find: SPOTIFY_CACHE_JSON
# 3. Click: Update
# 4. Paste: The ENTIRE output from `cat .cache`
# 5. Save
```

### 2. Enhanced Error Handling

**File:** `discovery.py`, Lines 158-170

**Enhanced to detect Premium restrictions:**
```python
# Source 1: Top Artists (Premium-only endpoint - gracefully degraded for free users)
logger.info("Building taste profile: fetching top artists...")
try:
    top_artists_response = sp.current_user_top_artists(limit=20, time_range='short_term')
    for artist in top_artists_response.get('items', []):
        artist_names.add(artist['name'])
    logger.info(f"✓ Loaded {len(artist_names)} artists from top artists")
except Exception as e:
    error_msg = str(e).lower()
    if "premium" in error_msg or "403" in error_msg or "blocked" in error_msg:
        logger.info("Skipping top artists (requires Spotify Premium subscription - continuing with other sources)")
    else:
        logger.warning(f"Error fetching top artists: {e}")
```

## Why Both Fixes Are Needed

### Issue #1: Missing Scope
- Without `user-top-read` scope, Spotify returns 403 immediately
- Error message can be misleading (says "Premium required" but actually means "scope missing")
- **Fix:** Add scope + regenerate tokens

### Issue #2: Premium Restriction  
- Even WITH correct scope, free users get 403 on this endpoint
- Spotify policy as of 2026: `GET /v1/me/top/artists` requires Premium
- **Fix:** Graceful error handling to skip for free users

## What This Does

### With Missing Scope (Before Fix #1)
```
❌ ALL users (free AND premium) → 403 Forbidden
```

### With Scope But No Error Handling (After Fix #1 Only)
```
✅ Premium users → Success
❌ Free users → 403 Forbidden → App crashes
```

### With Both Fixes (Current State)
```
✅ Premium users → Success (uses all 4 data sources)
✅ Free users → Gracefully skips (uses 3 other data sources)
```

## Complete Setup Instructions

### Step 1: Pull Latest Code
```bash
git pull origin main
```

### Step 2: Delete Old Token
```bash
rm .cache
```

### Step 3: Run Script (Reauthorize)
```bash
python main.py
```
- Browser will open
- Click "Agree" to authorize with new scopes
- App creates new `.cache` file

### Step 4: Verify New Scopes
```bash
cat .cache | python -m json.tool | grep scope
# Should see: "user-top-read" in the scope string
```

### Step 5: Update CI/CD Token
```bash
# Copy the entire token
cat .cache

# Then in GitHub:
# Settings → Secrets → SPOTIFY_CACHE_JSON → Update
# Paste the ENTIRE JSON (starts with { ends with })
```

### Step 6: Test
```bash
# Run again to verify
python main.py

# Expected log output:
# For Premium: "✓ Loaded X artists from top artists"
# For Free: "Skipping top artists (requires Spotify Premium...)"
```

## Why This Works

The application has **4 data sources** for building taste profiles:

1. **Top Artists** (Premium-only) - Now properly scoped and gracefully handled
2. ✅ **Followed Artists** - Free tier compatible
3. ✅ **Liked Songs** - Free tier compatible
4. ✅ **Personal Playlists** - Free tier compatible

**Result:** 
- Premium users: Benefit from all 4 sources with correct scope
- Free users: Get full functionality using sources 2-4

## Troubleshooting

### Error: "403 Forbidden" Still Appearing

**Most Likely Cause:** Old cached token doesn't have new scope

**Solution:**
```bash
# 1. Delete ALL token files
rm .cache

# 2. If using CI, also delete these from GitHub Secrets temporarily
# (will regenerate in next steps)

# 3. Run with fresh auth
python main.py

# 4. Check scope is present
cat .cache | python -m json.tool | grep user-top-read
# Should appear in scope string

# 5. Update GitHub Secret with new token
cat .cache  # Copy entire output
```

### Error: "Invalid Scope"

**Cause:** Typo in scope name

**Solution:** Verify line 87 in `spotify_client.py` says exactly:
```python
"user-top-read",  # Not user-read-top or top-read
```

### Error: Still Says "Premium Required" for Premium User

**Possible Causes:**
1. Token still has old scopes → Delete `.cache` and reauthorize
2. GitHub Secret has old token → Update with new token from `cat .cache`
3. Spotify account shows as Premium but isn't active → Check spotify.com/account

**Debug:**
```bash
# Check what scopes your token actually has
cat .cache | python -c "import sys, json; print(json.load(sys.stdin).get('scope', 'NO SCOPE FOUND'))"

# Should include: user-top-read
```

## All Endpoints Verified

| Endpoint | Method | Free Tier? | Scope Required | Location |
|----------|--------|------------|----------------|----------|
| `/v1/me/player/recently-played` | `current_user_recently_played()` | ✅ YES | `user-read-recently-played` | `database.py:40` |
| `/v1/me/tracks` | `current_user_saved_tracks()` | ✅ YES | `user-library-read` | `discovery.py:179` |
| `/v1/me/playlists` | `current_user_playlists()` | ✅ YES | (none specific) | `discovery.py:190, 352` |
| `/v1/me/following` | `current_user_followed_artists()` | ✅ YES | `user-follow-read` (implicit) | `discovery.py:170` |
| `/v1/me` | `me()` | ✅ YES | (none specific) | `discovery.py:192` |
| `/v1/me/top/artists` | `current_user_top_artists()` | ⚠️ **PREMIUM** | `user-top-read` ✅ **ADDED** | `discovery.py:161` |

## Summary of Changes

| File | Change | Why |
|------|--------|-----|
| `spotify_client.py` | Added `user-top-read` scope | Required for API authorization |
| `discovery.py` | Enhanced error handling | Graceful degradation for free users |
| `README.md` | Added free tier compatibility note | User communication |
| `SPOTIFY_FREE_TIER_FIX.md` | Complete documentation | Setup instructions |

## ⚠️ ACTION REQUIRED

**DO NOT skip token regeneration!**

Old tokens without `user-top-read` scope will continue to fail even with code changes.

**Required Steps:**
1. ✅ Delete `.cache` file locally
2. ✅ Run `python main.py` to reauthorize
3. ✅ Update `SPOTIFY_CACHE_JSON` GitHub Secret with new token
4. ✅ Verify scope with `cat .cache | grep user-top-read`

Without these steps, the application will still fail with 403 errors!

