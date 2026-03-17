# GitHub Secrets Setup: Quick Visual Guide

## Problem: "Failed to decode SPOTIFY_CACHE_JSON"

This happens when the JSON secret contains extra whitespace or is incorrectly formatted.

## Solution Steps

### Step 1: Export Your Token (Local Machine)

```bash
$ cat .cache
{"access_token":"BQD...","token_type":"Bearer","expires_in":3600,"refresh_token":"AQA...","scope":"...","expires_at":1234567890.123456}
```

**Key:** The output should be ONE LINE starting with `{` and ending with `}`

### Step 2: Copy to GitHub Secrets (Web UI)

1. Go to: **GitHub Repo → Settings → Secrets and variables → Actions**

2. Click **"New repository secret"**

3. Fill in:
   - **Name:** `SPOTIFY_CACHE_JSON`
   - **Value:** *(Paste the ENTIRE output from Step 1)*

4. Verify BEFORE clicking "Add secret":
   ```
   ✅ Value starts with {
   ✅ Value ends with }
   ✅ No extra quotes around the JSON
   ✅ Entire content is pasted
   ```

5. Click **"Add secret"**

### Step 3: Test It

```
GitHub → Actions → Unplayed Discovery Engine → Run workflow
```

## Common Mistakes

### ❌ WRONG: Extra Quotes
```
"{\"access_token\": \"BQD...\", ...}"
```
**Problem:** Secret has quotes wrapping it

**Fix:** Remove the outer quotes

---

### ❌ WRONG: Only Token Value
```
BQD...
```
**Problem:** Just copying the access_token, not the full JSON

**Fix:** Copy the ENTIRE output from `cat .cache` including `{` and `}`

---

### ❌ WRONG: Extra Whitespace
```
{
  "access_token": "BQD...",
  ...
}
```
**Problem:** Newlines and indentation from pretty-printing

**Fix:** Use `cat .cache` output directly (no formatting)

---

### ✅ CORRECT: Full JSON String
```
{"access_token":"BQD...","token_type":"Bearer","expires_in":3600,"refresh_token":"AQA...","scope":"...","expires_at":1234567890.123456}
```
**Why it works:** Complete JSON, no extra quotes, no extra whitespace

---

## If Still Failing

1. **Verify locally:**
   ```bash
   python -c "import json; json.load(open('.cache'))" && echo "✓ Valid"
   ```

2. **Check GitHub Secret:**
   - Go to Settings → Secrets
   - Click pencil icon next to `SPOTIFY_CACHE_JSON`
   - Scroll to see the full value
   - Verify it matches format above

3. **Delete and recreate:**
   - Delete the secret
   - Run `cat .cache` again
   - Paste the fresh output
   - Add secret

4. **See full troubleshooting:**
   - Read `SPOTIFY_TROUBLESHOOTING.md` for detailed debugging

---

## The Code Will Now Handle It

Updated `spotify_client.py` includes:
- ✅ `.strip()` to remove whitespace
- ✅ Better error messages showing what went wrong
- ✅ Debug hints pointing to documentation

If something is wrong, the error log will tell you exactly what to fix!
