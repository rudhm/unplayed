# 🎵 Hybrid Discovery System - Quick Start Guide

## What's New?

The Unplayed discovery engine has been **refactored into a hybrid system** that eliminates Spotify Premium dependencies and 403 Forbidden errors.

### Old System (Spotify-Only)
❌ Required Spotify Premium for user history
❌ 403 Forbidden errors for free-tier users
❌ Limited to Spotify's recommendation engine

### New System (Hybrid)
✅ Works with **Spotify Free** accounts
✅ Uses **Last.fm** for music intelligence
✅ **Optional** local Spotify exports for personalization
✅ Spotify API used **only** for final playlist output

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Get Last.fm Credentials
1. Go to: https://www.last.fm/api/account/create
2. Create an API account (free)
3. Note your **API Key** and **Username**

### Step 2: Update Configuration
Edit your `.env` file:
```bash
# Last.fm (REQUIRED - primary intelligence)
LASTFM_API_KEY=your_api_key_here
LASTFM_USERNAME=your_username_here

# Spotify (existing credentials - now only for playlist output)
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Spotify Export (OPTIONAL - enhances personalization)
# Download at: https://www.spotify.com/account/privacy/
SPOTIFY_EXPORT_PATH=/path/to/your/spotify/export/folder
```

### Step 3: Run Discovery Engine
```bash
python main.py
```

That's it! The system will:
1. Build your taste profile from Last.fm
2. Generate discovery candidates
3. Filter out tracks you've already played (if export configured)
4. Create/update "Unplayed Discoveries" playlist in Spotify

---

## 📊 How It Works

### The Hybrid Pipeline

```
┌─────────────────────────────────────────────────┐
│ Phase 1: TASTE PROFILE (Last.fm)               │
│ • Fetch your top 50 artists                    │
│ • Expand with similar artists                  │
│ • Result: 50-150 artist pool                   │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Phase 2: CANDIDATE GENERATION (Last.fm)        │
│ • Fetch top tracks for each artist             │
│ • Collect metadata (playcount, listeners)      │
│ • Result: 200-300 candidate tracks             │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Phase 3: FILTERING & SCORING (Local)           │
│ • Filter out played tracks from exports        │
│ • Score: 60% popularity + 40% taste fit        │
│ • Boost artists in your play history           │
│ • Result: Top 40 recommendations               │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Phase 4: OUTPUT (Spotify API)                  │
│ • Search Spotify to resolve track URIs        │
│ • Fuzzy match validation                       │
│ • Update "Unplayed Discoveries" playlist       │
│ • Result: Fresh playlist ready to listen!      │
└─────────────────────────────────────────────────┘
```

---

## ❓ FAQ

### Do I need Spotify Premium?
**No!** The system now works with Spotify Free accounts. Spotify is only used for:
- Searching track names → URIs
- Managing the playlist

### Do I need a Last.fm account?
**Yes.** Last.fm is the "brain" of the system. You need:
- A Last.fm API key (free)
- A Last.fm username with scrobbling history

If you don't have scrobbling history yet, start using Last.fm for a few weeks to build up data.

### Do I need Spotify GDPR exports?
**Optional but recommended.** Without exports:
- System still works fine
- May recommend tracks you've already heard

With exports:
- Filters out all tracks in your play history
- Boosts artists you listen to frequently
- Better personalization

### How do I get Spotify exports?
1. Go to: https://www.spotify.com/account/privacy/
2. Request your data (takes a few days)
3. Extract `StreamingHistory*.json` files
4. Set `SPOTIFY_EXPORT_PATH` in `.env`

### Why is it slower than before?
The new system makes 30-50 Last.fm API calls (vs 10-20 Spotify calls). However:
- **Much more reliable** (no 403 errors)
- **Works for all users** (not just Premium)
- **Better discovery** (Last.fm has broader music database)

Typical runtime: 10-20 seconds

### What if I get errors?
Common issues and solutions:

**"No top artists found"**
- Your Last.fm username doesn't have scrobbling history
- Solution: Use Last.fm for a while, or try a different username

**"403 Forbidden" from Spotify**
- Rate limiting on search API (rare)
- Solution: Built-in retry logic handles this; some tracks may not resolve

**"Missing LASTFM_API_KEY"**
- Last.fm credentials not configured
- Solution: Add credentials to `.env` file

---

## 🧪 Testing

Run the integration test suite to verify everything works:
```bash
python test_hybrid_system.py
```

This tests:
- ✅ Text normalization utilities
- ✅ Last.fm API connectivity
- ✅ Spotify export loading
- ✅ URI resolution
- ✅ Full pipeline (dry run)

---

## 📚 Documentation

- **`docs/HYBRID_ARCHITECTURE.md`** - Complete technical documentation
- **`test_hybrid_system.py`** - Integration tests and examples
- **`.env.example`** - Configuration reference

---

## 🔄 Migration from Old Version

If you're upgrading from the old Spotify-only system:

### What stays the same
- ✅ Same command: `python main.py`
- ✅ Same output: "Unplayed Discoveries" playlist
- ✅ Same workflow

### What's new
- 🆕 Need to configure Last.fm credentials
- 🆕 Optionally configure Spotify export path
- 🆕 Faster, more reliable discovery

### Backward compatibility
The old implementation is preserved in `discovery_old.py` if you need to reference it.

---

## 🎯 Next Steps

1. **Configure Last.fm** - Get your API key and username
2. **Update .env** - Add Last.fm credentials
3. **Run once** - Test with `python main.py`
4. **Optional**: Download Spotify exports for better filtering
5. **Enjoy**: Fresh music discoveries without Premium restrictions!

---

## 🐛 Troubleshooting

### Low resolution rate
**Problem**: Many tracks fail to resolve to Spotify URIs

**Solutions**:
- Last.fm and Spotify catalogs don't always match perfectly
- System uses fuzzy matching (85% similarity threshold)
- To be more lenient, edit `spotify_resolver.py` and change threshold to `0.80`

### Empty playlist
**Problem**: All candidates were filtered out

**Solutions**:
- Try expanding artist pool (increase `top_artists_limit` in code)
- Check if export path is correct
- Try without export filtering first

### Slow performance
**Problem**: Takes too long to generate recommendations

**Solutions**:
- Reduce `target` parameter (default 40 → 20 tracks)
- Reduce artist pool size
- Check network connectivity to Last.fm

---

## 💡 Tips

1. **First run**: May take 15-20 seconds as caches warm up
2. **Subsequent runs**: Faster due to caching
3. **Best results**: Use system regularly to build Last.fm history
4. **Export updates**: Re-download Spotify exports periodically for accurate filtering

---

## 🙋 Support

- **Issues**: Open a GitHub issue with error logs
- **Questions**: Check `docs/HYBRID_ARCHITECTURE.md` for technical details
- **Tests**: Run `test_hybrid_system.py` to diagnose issues

---

**Enjoy your new music discoveries! 🎧**
