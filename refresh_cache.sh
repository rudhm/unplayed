#!/bin/bash
# Helper script to refresh Spotify authentication cache

set -e

echo "🔄 Refreshing Spotify Authentication Cache"
echo "=========================================="

# Check if .cache exists
if [ -f .cache ]; then
    echo "📁 Found existing .cache file"
    echo "🗑️  Removing old cache..."
    rm .cache
    echo "✓ Old cache removed"
else
    echo "📁 No existing .cache file found"
fi

echo ""
echo "🔐 Starting authentication flow..."
echo "   (This will open your browser for Spotify login)"
echo ""

# Run a simple test to trigger auth
python verify_auth.py

if [ -f .cache ]; then
    echo ""
    echo "✓ Authentication successful! New .cache file created"
    echo ""
    echo "📤 To update GitHub Actions secret, run:"
    echo "   gh secret set SPOTIFY_CACHE_JSON < .cache"
else
    echo ""
    echo "✗ Authentication failed - no .cache file was created"
    exit 1
fi
