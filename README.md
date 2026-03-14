# 🎧 Unplayed: A Resilient Spotify Discovery Engine
Spotify recently locked down their recommendation API, so I built my own.

This is a personalized music discovery engine I built (with the help of an AI agent) to solve a personal problem: I wanted a daily playlist of truly unplayed songs that perfectly matched my taste, without getting stuck in a recommendation echo chamber.

Because Spotify deprecated genre tags and locked down their graph endpoints, this script uses a hybrid architecture: it reads your listening history from Spotify, fetches genre tags from Last.fm, mathematically scores candidates, and cross-references a local SQLite database to guarantee you've never heard the songs before.

✨ Features
The Last.fm Bridge: Bypasses Spotify's API restrictions by mapping your top artists to Last.fm's open genre tags.

V2 Scoring Algorithm: Evaluates a pool of 120+ candidate tracks and ranks them based on a custom freshness and popularity mathematical formula.

Artist Diversity Limits: Strictly enforces a max 2 tracks per artist rule so your playlist never gets flooded by one band.

80/20 Intelligent Mix: 80% of the playlist is hyper-targeted to your exact taste profile, while 20% explores random wildcard genres to keep things fresh.

True "Unplayed" Guarantee: Uses a local history.db SQLite database to remember every song it has ever given you, ensuring zero repeats.

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
