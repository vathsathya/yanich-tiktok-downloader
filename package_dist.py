#!/usr/bin/env python3
"""
Cross-Platform Production Release Packager
Creates standalone distribution archives with Extension, Readme, and Launchers.
"""
import os
import sys
import shutil
import zipfile
import tarfile
import platform
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
EXT_DIR = os.path.join(BASE_DIR, "extension")
APP_DIST_DIR = os.path.join(DIST_DIR, "TikTokDownloader")

def sync_extension_version():
    """Synchronizes extension/manifest.json with version.py."""
    manifest_path = os.path.join(EXT_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        try:
            from version import VERSION
        except ImportError:
            return
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["version"] = VERSION
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        print(f"[*] Synchronized Chrome Extension manifest version to v{VERSION}")
    except Exception as e:
        print(f"[-] Failed to sync manifest version: {e}")

def pack_extension():
    """Packs the Chrome Extension into a clean zip archive."""
    if not os.path.exists(EXT_DIR):
        print("[-] Extension directory not found, skipping extension packaging.")
        return None
    
    sync_extension_version()
    zip_path = os.path.join(DIST_DIR, "TikTok-Extractor-Extension.zip")
    print(f"[*] Packaging Chrome Extension to: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(EXT_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, EXT_DIR)
                zf.write(full_path, arcname=os.path.join("extension", rel_path))
    print(f"[+] Extension packaged successfully: {zip_path}")
    return zip_path

def create_dist_readme():
    """Generates distribution instructions inside the release folder."""
    readme_content = """===========================================================
 TikTok Drama & Video Batch Downloader Pro (Production Build)
===========================================================

1. HOW TO RUN:
   - Linux: Execute './TikTokDownloader'
   - Windows: Double-click 'TikTokDownloader.exe'

2. 1-CLICK BROWSER INTEGRATION:
   - Unpack 'TikTok-Extractor-Extension.zip'
   - In Chrome/Edge/Brave: Open chrome://extensions -> Enable 'Developer Mode' -> 'Load unpacked'
   - Or open app and follow '1-Click Browser Setup' at http://127.0.0.1:54321/setup

3. REPOSITORY & UPDATES:
   https://github.com/vathsathya/yanich-tiktok-downloader
===========================================================
"""
    readme_path = os.path.join(APP_DIST_DIR, "README.txt")
    if os.path.exists(APP_DIST_DIR):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

def create_linux_desktop_file():
    """Creates a standard Linux .desktop launcher entry."""
    if sys.platform != "linux" or not os.path.exists(APP_DIST_DIR):
        return
    desktop_content = """[Desktop Entry]
Type=Application
Name=TikTok Downloader
Comment=TikTok Drama & Video Batch Downloader
Exec=./TikTokDownloader
Icon=video-display
Terminal=false
Categories=Network;AudioVideo;
"""
    desktop_path = os.path.join(APP_DIST_DIR, "tiktok-downloader.desktop")
    with open(desktop_path, "w", encoding="utf-8") as f:
        f.write(desktop_content)
    os.chmod(desktop_path, 0o755)

def pack_release():
    """Creates tar.gz / zip for the target operating system."""
    if not os.path.exists(APP_DIST_DIR):
        print(f"[-] Application build directory not found at: {APP_DIST_DIR}")
        return

    create_dist_readme()
    ext_zip = pack_extension()

    # Also copy extension zip into the app dist folder
    if ext_zip and os.path.exists(ext_zip):
        shutil.copy(ext_zip, APP_DIST_DIR)

    current_os = platform.system().lower()
    arch = platform.machine().lower() or "x64"

    if current_os == "windows":
        archive_name = f"TikTokDownloader-Windows-{arch}.zip"
        archive_path = os.path.join(DIST_DIR, archive_name)
        print(f"[*] Compressing Windows release archive: {archive_path}")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(APP_DIST_DIR):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, DIST_DIR)
                    zf.write(full_path, arcname=rel_path)
        print(f"[+] Windows Release Archive Created: {archive_path}")

    elif current_os == "linux":
        create_linux_desktop_file()
        archive_name = f"TikTokDownloader-Linux-{arch}.tar.gz"
        archive_path = os.path.join(DIST_DIR, archive_name)
        print(f"[*] Compressing Linux release archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(APP_DIST_DIR, arcname="TikTokDownloader")
        print(f"[+] Linux Release Archive Created: {archive_path}")

if __name__ == "__main__":
    pack_release()
