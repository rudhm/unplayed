# 🎧 Unplayed: Discover Songs You've Actually Never Heard

Spotify recommends songs you might like, but it still repeats artists you've already heard. I built Unplayed to discover songs I've never played before, using the Spotify API and an automated discovery engine.

The problem with Spotify's recommendations is real: you get stuck in loops with the same artists, the algorithm doesn't remember what you've actually played, and "personalized" starts to feel formulaic. This script solves that by building a hybrid system that reads your listening history, discovers new tracks from genres you love, and maintains a permanent memory of everything it's ever recommended—so you never get the same song twice.

## ✨ Features

**The Last.fm Bridge**: Spotify locked down their APIs, so we work around it. We map your top artists to Last.fm's open genre database to find what you actually want to hear.

**V2 Scoring Algorithm**: Evaluates 120+ candidate songs and ranks them using a custom formula that balances freshness (new songs) with what matches your taste.

**No Artist Fatigue**: Enforces a max of 2 songs per artist per discovery, so you don't get bored of the same band.

**80/20 Mix**: 80% laser-focused on your exact taste, 20% random wildcard picks to surprise you with something unexpected.

**True Unplayed Guarantee**: Uses a local SQLite database to remember every single song we've ever given you. Zero repeats. Ever.

🛠️ Prerequisites
To run this yourself, you will need:

Python installed (this project uses uv for package management).

A Spotify Developer App (Client ID and Client Secret).

A Last.fm API Key (Free to generate).

🚀 Local Setup
1. Clone the repository and install dependencies
```bash
git clone https://github.com/rudhm/unplayed
cd unplayed
uv sync
```

2. Set up your Environment Variables
Create a .env file in the root directory and add your keys:
```env
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
LASTFM_API_KEY=your_lastfm_api_key
```

3. Run the Engine
```bash
uv run main.py
```
Note: On your very first run, your browser will open asking you to grant Spotify permissions. Once approved, a .cache file will be generated locally to keep you logged in.

☁️ Automating with GitHub Actions (Optional)
I designed this to run automatically every morning using GitHub Actions. If you fork this repo, just add the following to your Repository Secrets (Settings > Secrets and variables > Actions):

SPOTIPY_CLIENT_ID

SPOTIPY_CLIENT_SECRET

SPOTIPY_REDIRECT_URI

LASTFM_API_KEY

SPOTIFY_CACHE_JSON (Paste the exact contents of your local .cache file here so the cloud server can authenticate as you).
