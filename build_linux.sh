#!/usr/bin/env bash
set -e

echo "=================================================="
echo " Building TikTok Downloader for Linux (Production)"
echo "=================================================="

# Ensure virtualenv exists
if [ ! -d ".venv" ]; then
    echo "[*] Initializing virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

# Ensure pyinstaller is installed
if ! .venv/bin/python -c "import PyInstaller" &>/dev/null; then
    echo "[*] Installing PyInstaller..."
    .venv/bin/pip install pyinstaller
fi

# Clean previous build artifacts
echo "[*] Cleaning old build artifacts..."
rm -rf build dist

# Run PyInstaller Build
echo "[*] Compiling Standalone Linux Binary..."
.venv/bin/pyinstaller --clean TikTokDownloader.spec

# Package Distribution
echo "[*] Creating Distribution Archives..."
.venv/bin/python package_dist.py

echo "=================================================="
echo " Linux Production Build Complete!"
echo " Output files available in dist/"
echo "=================================================="
