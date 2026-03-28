# QUICK START: Fix Spotify Premium Error

## TL;DR - Run These Commands

```bash
# 1. Delete old token (REQUIRED)
rm .cache

# 2. Regenerate with new scopes
python main.py
# Browser opens → Click "Agree"

# 3. Verify the fix
python3 test_top_artists.py

# 4. Update GitHub Secret (if using CI/CD)
cat .cache  # Copy entire output
# Paste into: GitHub → Settings → Secrets → SPOTIFY_CACHE_JSON
```

That's it! ✅

---

## What Changed?

**Added missing OAuth scope:** `user-top-read`

Without this scope, Spotify returns 403 for ALL users (free and Premium).

---

## Expected Results

### Premium Users
```
✅ TEST PASSED - No Premium restriction detected
Top 5 Artists:
  1. Artist Name
  2. Artist Name
  ...
```

### Free Users (Expected!)
```
🔴 ROOT CAUSE: Premium Subscription Required
   This is expected for free tier users.
   The main app will gracefully skip this data source.
```

**Both work!** The app has 3 other data sources for free users.

---

## Troubleshooting

### Still Getting 403?

Check your token has the new scope:
```bash
cat .cache | python3 -c "import sys, json; print(json.load(sys.stdin).get('scope', ''))" | grep user-top-read
```

If empty → Delete `.cache` and regenerate again.

---

## Files Modified

- `spotify_client.py` - Added `user-top-read` scope
- `discovery.py` - Added debug logging + Premium detection
- `test_top_artists.py` - NEW test script
- `VERIFICATION_GUIDE.md` - NEW detailed testing guide

---

## Need Help?

See `VERIFICATION_GUIDE.md` for detailed step-by-step testing instructions.
