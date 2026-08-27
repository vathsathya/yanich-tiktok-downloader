@echo off
title TikTok Downloader - Production Windows Build
echo ==================================================
echo  Building TikTok Downloader for Windows (Production)
echo ==================================================

if not exist ".venv" (
    echo [*] Initializing virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo [*] Installing PyInstaller...
    pip install pyinstaller
)

echo [*] Cleaning old build artifacts...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo [*] Compiling Standalone Windows Executable (.exe)...
pyinstaller --clean TikTokDownloader.spec

echo [*] Creating Distribution Archives...
python package_dist.py

echo ==================================================
echo  Windows Production Build Complete!
echo  Output files available in dist\
echo ==================================================
pause
