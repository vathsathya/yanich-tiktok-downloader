import os
import re
import sys
import json
import time
import html
import queue
import random
import socket
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from requests.adapters import HTTPAdapter
import webbrowser
from PIL import Image, ImageTk

# ----------------- Configuration & Constants -----------------
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 54321
SINGLE_INSTANCE_PORT = 54320
MAX_AUTO_RETRIES = 2

class SingleInstanceLock:
    """Enforces a single application instance using a dedicated localhost socket lock."""
    def __init__(self, port=SINGLE_INSTANCE_PORT):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_locked = False

    def acquire(self):
        try:
            self.sock.bind(("127.0.0.1", self.port))
            self.sock.listen(5)
            self.is_locked = True
            return True
        except socket.error:
            return False

    def release(self):
        if self.is_locked:
            try:
                self.sock.close()
            except Exception:
                pass
            self.is_locked = False

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller bundled apps."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# Module-Level Precompiled Regex Patterns for High Performance
TIKTOK_URL_RE = re.compile(r'https?://(?:www\.|vt\.|vm\.|m\.)?tiktok\.com/[^\s"\'<>]+', re.IGNORECASE)
FILENAME_CLEAN_RE = re.compile(r'[\\/:*?"<>|\n\r\t]')
WHITESPACE_RE = re.compile(r'\s+')

# Realistic Browser Headers for Anti-Bot Resilience
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Referer": "https://www.tiktok.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9"
}

def create_http_session(pool_size=10):
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    adapter = HTTPAdapter(
        pool_connections=pool_size,
        pool_maxsize=pool_size,
        max_retries=2
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def resolve_tiktok_shortlink(url, session=None):
    """Resolves shortlinks like vt.tiktok.com or vm.tiktok.com to canonical URL."""
    clean_url = url.strip()
    if "vt.tiktok.com" in clean_url or "vm.tiktok.com" in clean_url:
        sess = session or requests.Session()
        try:
            resp = sess.head(clean_url, allow_redirects=True, timeout=(4, 10))
            if resp.url and "tiktok.com" in resp.url:
                return resp.url
        except Exception:
            try:
                resp = sess.get(clean_url, allow_redirects=True, timeout=(4, 10), stream=True)
                if resp.url and "tiktok.com" in resp.url:
                    return resp.url
            except Exception:
                pass
    return clean_url

def extract_tiktok_metadata(url, session=None):
    """Multi-tier resilient metadata extractor with automatic failover."""
    sess = session or requests.Session()
    clean_url = resolve_tiktok_shortlink(url, sess)

    # Tier 1: TikWM Primary API
    try:
        api_url = f"https://www.tikwm.com/api/?url={requests.utils.quote(clean_url)}"
        resp = sess.get(api_url, timeout=(4, 16))
        if resp.status_code == 200:
            data = resp.json()
            if data and data.get("code") == 0 and "data" in data and "play" in data["data"]:
                d = data["data"]
                return {
                    "success": True,
                    "video_url": d["play"],
                    "cover_url": d.get("cover") or d.get("origin_cover"),
                    "title": (d.get("title") or "").strip(),
                    "author": d.get("author", {}).get("nickname", "TikTok Creator"),
                    "source": "TikWM"
                }
    except Exception:
        pass

    # Tier 2: TikWM Backup Mirror
    try:
        api_url2 = f"https://tikwm.com/api/?url={requests.utils.quote(clean_url)}"
        resp2 = sess.get(api_url2, timeout=(4, 16))
        if resp2.status_code == 200:
            data2 = resp2.json()
            if data2 and data2.get("code") == 0 and "data" in data2 and "play" in data2["data"]:
                d = data2["data"]
                return {
                    "success": True,
                    "video_url": d["play"],
                    "cover_url": d.get("cover") or d.get("origin_cover"),
                    "title": (d.get("title") or "").strip(),
                    "author": d.get("author", {}).get("nickname", "TikTok Creator"),
                    "source": "TikWM-Mirror"
                }
    except Exception:
        pass

    # Tier 3: Tiklydown Open API Fallback
    try:
        api_url3 = f"https://api.tiklydown.eu.org/api/download?url={requests.utils.quote(clean_url)}"
        resp3 = sess.get(api_url3, timeout=(5, 18))
        if resp3.status_code == 200:
            data3 = resp3.json()
            video_url = data3.get("video", {}).get("noWatermark") or data3.get("video", {}).get("watermark")
            if video_url:
                return {
                    "success": True,
                    "video_url": video_url,
                    "cover_url": data3.get("video", {}).get("cover"),
                    "title": (data3.get("title") or "").strip(),
                    "author": data3.get("author", {}).get("name", "TikTok Creator"),
                    "source": "Tiklydown"
                }
    except Exception:
        pass

    return {"success": False, "error": "Extraction failed across all API providers"}

# Modern Sleek Dark Palette
THEME = {
    "bg": "#090d16",
    "card_bg": "#121929",
    "card_border": "#1e293b",
    "input_bg": "#0a0f1d",
    "input_fg": "#f8fafc",
    "text_primary": "#f8fafc",
    "text_secondary": "#94a3b8",
    "accent_cyan": "#06b6d4",
    "accent_emerald": "#10b981",
    "accent_rose": "#e11d48",
    "accent_amber": "#d97706",
    "accent_purple": "#a855f7",
    "btn_dark_bg": "#1e293b",
    "btn_dark_hover": "#334155",
    "log_bg": "#080c14",
    "progress_track": "#0a0f1d",
    "progress_fill": "#06b6d4"
}

# ----------------- Local HTTP Bridge Server -----------------
class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class BridgeRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _set_cors_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_cors_headers(200)

    def do_GET(self):
        if self.path == "/api/ping":
            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "app": "TikTokDownloader"}).encode("utf-8"))
        elif self.path == "/extractor.js":
            extractor_path = get_resource_path("extractor.js")
            if os.path.exists(extractor_path):
                self._set_cors_headers(200, content_type="application/javascript; charset=utf-8")
                with open(extractor_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._set_cors_headers(404)
                self.wfile.write(b"// Not found")
        elif self.path in ["/setup", "/", "/setup.html"]:
            bookmarklet_path = get_resource_path("bookmarklet.txt")
            if os.path.exists(bookmarklet_path):
                with open(bookmarklet_path, "r", encoding="utf-8") as f:
                    bookmarklet_code = f.read().strip()
            else:
                bookmarklet_code = "javascript:(async function(){alert('Please check bookmarklet.txt');})();"
            
            escaped_code = html.escape(bookmarklet_code, quote=True)
            html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TikTok Downloader - 1-Click Browser Setup</title>
    <style>
        body {{ background: #090d16; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
        .card {{ background: #121929; border: 1px solid #1e293b; border-radius: 16px; padding: 32px; max-width: 620px; width: 100%; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }}
        h1 {{ color: #06b6d4; font-size: 24px; margin-top: 0; display: flex; align-items: center; gap: 10px; }}
        .drag-box {{ background: #0a0f1d; border: 2px dashed #06b6d4; border-radius: 12px; padding: 24px; text-align: center; margin: 24px 0; }}
        .drag-btn {{ display: inline-block; background: #06b6d4; color: #090d16; font-size: 16px; font-weight: bold; padding: 14px 28px; border-radius: 30px; text-decoration: none; box-shadow: 0 4px 20px rgba(6,182,212,0.4); cursor: grab; }}
        .drag-btn:hover {{ background: #22d3ee; }}
        .copy-box {{ background: #0a0f1d; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; margin-top: 16px; display: flex; gap: 8px; align-items: center; }}
        .copy-input {{ background: transparent; border: none; color: #64748b; font-family: monospace; font-size: 11px; flex: 1; outline: none; }}
        .copy-btn {{ background: #1e293b; color: #06b6d4; border: 1px solid #334155; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 12px; white-space: nowrap; }}
        .copy-btn:hover {{ background: #334155; color: #38bdf8; }}
        .step {{ margin: 12px 0; line-height: 1.6; color: #94a3b8; font-size: 14px; }}
        .step b {{ color: #f8fafc; }}
        .badge {{ background: #064e3b; color: #34d399; font-size: 12px; font-weight: bold; padding: 4px 10px; border-radius: 20px; }}
        .footer {{ margin-top: 24px; border-top: 1px solid #1e293b; padding-top: 16px; display: flex; justify-content: space-between; font-size: 13px; color: #64748b; }}
    </style>
</head>
<body>
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h1>🚀 1-Click Browser Setup</h1>
            <span class="badge">App Connected</span>
        </div>
        <p style="color:#94a3b8; margin: 6px 0 20px 0;">Drag the button below directly into your Bookmarks Bar (<b>Ctrl + Shift + B</b>):</p>
        
        <div class="drag-box">
            <a class="drag-btn" href="{escaped_code}">🚀 Send to TikTok Downloader</a>
            <p style="margin: 12px 0 0 0; font-size: 12px; color: #06b6d4;">👆 Drag & Drop this button to your Bookmarks bar with your mouse!</p>
        </div>

        <div class="step"><b>1.</b> Press <b>Ctrl + Shift + B</b> on your browser to show the Bookmarks bar.</div>
        <div class="step"><b>2.</b> Drag the cyan button above into the Bookmarks bar.</div>
        <div class="step"><b>3.</b> Go to any TikTok drama series page (About tab), and click the bookmark!</div>

        <div class="copy-box">
            <input type="text" class="copy-input" readonly value="{escaped_code}" id="codeVal" />
            <button class="copy-btn" id="copyBtn" onclick="copyCode()">📋 Copy Code</button>
        </div>
        
        <div class="footer">
            <span>Desktop Local Bridge: <b>54321</b></span>
            <a href="https://www.tiktok.com" target="_blank" style="color:#06b6d4; text-decoration:none; font-weight:bold;">Open TikTok ↗</a>
        </div>
    </div>
    <script>
        function copyCode() {{
            const val = document.getElementById('codeVal').value;
            navigator.clipboard.writeText(val);
            const btn = document.getElementById('copyBtn');
            btn.textContent = '✅ Copied!';
            btn.style.color = '#34d399';
            setTimeout(() => {{
                btn.textContent = '📋 Copy Code';
                btn.style.color = '#06b6d4';
            }}, 2000);
        }}
    </script>
</body>
</html>"""
            self._set_cors_headers(200, content_type="text/html; charset=utf-8")
            self.wfile.write(html_page.encode("utf-8"))
        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/receive-links":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                
                items = []
                series_title = ""
                try:
                    data = json.loads(body)
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        series_title = data.get("title", "")
                        if "episodes" in data and isinstance(data["episodes"], list):
                            items = data["episodes"]
                        elif "urls" in data and isinstance(data["urls"], list):
                            items = data["urls"]
                except Exception:
                    items = [line.strip() for line in body.split("\n") if line.strip()]

                if hasattr(self.server, "app") and self.server.app:
                    self.server.app.root.after(0, lambda it=items, t=series_title: self.server.app.on_links_received_from_bridge(it, t))

                self._set_cors_headers(200)
                self.wfile.write(json.dumps({"status": "success", "count": len(items)}).encode("utf-8"))
            except Exception as e:
                self._set_cors_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/bring-to-front":
            if hasattr(self.server, "app") and self.server.app:
                self.server.app.root.after(0, self.server.app.bring_window_to_front)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


# ----------------- Modern Progress Bar Component -----------------
class ModernProgressBar(tk.Canvas):
    def __init__(self, parent, height=24, **kwargs):
        super().__init__(parent, height=height, bg=THEME["progress_track"], highlightthickness=1, highlightbackground=THEME["card_border"], **kwargs)
        self.progress = 0.0
        self.text_overlay = "0% (0/0)"
        self.bind("<Configure>", self.draw)

    def set_progress(self, current, total, custom_text=None):
        self.progress = (current / total) if total > 0 else 0.0
        self.progress = max(0.0, min(1.0, self.progress))
        percent = self.progress * 100
        self.text_overlay = custom_text or f"{percent:.1f}% ({current}/{total})"
        self.draw()

    def draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return

        fill_width = int(w * self.progress)
        fill_color = THEME["accent_emerald"] if self.progress >= 1.0 else THEME["progress_fill"]
        if fill_width > 0:
            self.create_rectangle(0, 0, fill_width, h, fill=fill_color, width=0)

        text_color = "#ffffff" if self.progress > 0.4 else THEME["text_secondary"]
        self.create_text(w / 2, h / 2, text=self.text_overlay, fill=text_color, font=("Arial", 9, "bold"))


# ----------------- Add Links Modal Dialog -----------------
class AddLinksModal(tk.Toplevel):
    def __init__(self, parent, on_load_callback, auto_paste=False):
        super().__init__(parent)
        self.title("➕ Add TikTok Video Links")
        self.geometry("620x480")
        self.minsize(520, 400)
        self.configure(bg=THEME["bg"])
        self.transient(parent)
        self.grab_set()

        self.on_load_callback = on_load_callback
        self.setup_ui()
        if auto_paste:
            self.after(80, self.paste_clipboard)

    def setup_ui(self):
        # 1. Header (Top)
        top = tk.Frame(self, bg=THEME["card_bg"], padx=14, pady=10, highlightbackground=THEME["card_border"], highlightthickness=1)
        top.pack(fill="x", side="top")
        tk.Label(top, text="Paste TikTok Video / Drama Links", bg=THEME["card_bg"], fg=THEME["accent_cyan"], font=("Arial", 11, "bold")).pack(side="left")
        self.modal_count_lbl = tk.Label(top, text="0 Links Detected", bg="#1e293b", fg=THEME["accent_cyan"], font=("Arial", 9, "bold"), padx=8, pady=2)
        self.modal_count_lbl.pack(side="right")

        # 2. Action Buttons (Bottom - packed BEFORE body to always stay visible)
        bottom = tk.Frame(self, bg=THEME["card_bg"], padx=14, pady=10, highlightbackground=THEME["card_border"], highlightthickness=1)
        bottom.pack(fill="x", side="bottom")

        ttk.Button(bottom, text="📋 Paste Clipboard", command=self.paste_clipboard, style="DarkBtn.TButton").pack(side="left", padx=3)
        ttk.Button(bottom, text="📂 Open File (.txt / .json)", command=self.load_any_file, style="DarkBtn.TButton").pack(side="left", padx=3)
        ttk.Button(bottom, text="Clear", command=self.clear_text, style="DarkBtn.TButton").pack(side="left", padx=3)

        ttk.Button(bottom, text="Cancel", command=self.destroy, style="DarkBtn.TButton").pack(side="right", padx=3)
        ttk.Button(bottom, text="📥 Load to Queue", command=self.submit_links, style="PrimaryBtn.TButton").pack(side="right", padx=4)

        # 3. Text Area & Title Box (Middle - takes remaining space)
        body = tk.Frame(self, bg=THEME["bg"], padx=14, pady=10)
        body.pack(fill="both", expand=True)

        title_box = tk.Frame(body, bg=THEME["bg"])
        title_box.pack(fill="x", pady=(0, 8))
        tk.Label(title_box, text="Drama / Series Title (Optional):", bg=THEME["bg"], fg=THEME["accent_cyan"], font=("Arial", 9, "bold")).pack(side="left", padx=(0, 6))
        self.series_title_var = tk.StringVar(value="")
        ttk.Entry(title_box, textvariable=self.series_title_var, style="Dark.TEntry").pack(side="left", fill="x", expand=True)

        text_container = tk.Frame(body, bg=THEME["input_bg"], highlightbackground=THEME["card_border"], highlightthickness=1)
        text_container.pack(fill="both", expand=True)

        self.url_text = tk.Text(text_container, wrap="none", font=("Consolas", 10), bg=THEME["input_bg"], fg=THEME["input_fg"], insertbackground=THEME["accent_cyan"], relief="flat", padx=8, pady=8)
        scroll_y = ttk.Scrollbar(text_container, orient="vertical", command=self.url_text.yview)
        scroll_x = ttk.Scrollbar(text_container, orient="horizontal", command=self.url_text.xview)
        self.url_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.url_text.pack(side="left", fill="both", expand=True)

        self.url_text.bind("<KeyRelease>", lambda e: self.update_modal_count())

    def update_modal_count(self):
        content = self.url_text.get("1.0", "end-1c")
        found = TIKTOK_URL_RE.findall(content)
        if not found:
            found = [line.strip() for line in content.split("\n") if line.strip().startswith("http")]
        self.modal_count_lbl.config(text=f"{len(found)} Links Detected")

    def clear_text(self):
        self.url_text.delete("1.0", "end")
        self.update_modal_count()

    def paste_clipboard(self):
        try:
            txt = self.clipboard_get()
            self.url_text.insert("insert", txt)
            self.update_modal_count()
        except Exception:
            pass

    def load_any_file(self):
        fpath = filedialog.askopenfilename(filetypes=[("All Supported", "*.txt;*.json"), ("Text Files", "*.txt"), ("JSON Files", "*.json"), ("All Files", "*.*")])
        if fpath:
            try:
                if fpath.endswith(".json"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        title = data.get("title") or data.get("series_title") or ""
                        if title:
                            self.series_title_var.set(title)
                        episodes = data.get("episodes") or data.get("items") or data.get("urls") or []
                        urls = []
                        for ep in episodes:
                            if isinstance(ep, dict):
                                urls.append(ep.get("url", ""))
                            elif isinstance(ep, str):
                                urls.append(ep)
                        self.url_text.delete("1.0", "end")
                        self.url_text.insert("1.0", "\n".join([u for u in urls if u]))
                    elif isinstance(data, list):
                        urls = [ep.get("url", "") if isinstance(ep, dict) else str(ep) for ep in data]
                        self.url_text.delete("1.0", "end")
                        self.url_text.insert("1.0", "\n".join([u for u in urls if u]))
                else:
                    with open(fpath, "r", encoding="utf-8") as f:
                        self.url_text.delete("1.0", "end")
                        self.url_text.insert("1.0", f.read())
                self.update_modal_count()
            except Exception as e:
                messagebox.showerror("File Error", f"Could not read file: {e}")

    def submit_links(self):
        content = self.url_text.get("1.0", "end-1c")
        found = TIKTOK_URL_RE.findall(content)
        if not found:
            found = [line.strip() for line in content.split("\n") if line.strip().startswith("http")]

        if not found:
            messagebox.showwarning("No Links Found", "Please paste or enter at least one valid TikTok URL.")
            return

        self.on_load_callback(found, series_title=self.series_title_var.get().strip())
        self.destroy()


# ----------------- Video Preview Modal -----------------
class VideoPreviewModal(tk.Toplevel):
    def __init__(self, parent, episodes_data, current_index=0):
        super().__init__(parent)
        self.title("🎬 Video Preview & Media Player")
        self.geometry("560x600")
        self.minsize(480, 520)
        self.configure(bg=THEME["bg"])
        self.transient(parent)

        self.episodes = episodes_data
        self.idx = max(0, min(len(episodes_data) - 1, current_index)) if episodes_data else 0
        self.photo_ref = None

        self.setup_ui()
        self.display_episode()

        # Keyboard Navigation Shortcuts
        self.bind("<Left>", lambda e: self.prev_episode())
        self.bind("<Right>", lambda e: self.next_episode())
        self.bind("<space>", lambda e: self.play_video())
        self.bind("<Escape>", lambda e: self.on_close())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.photo_ref = None
        self.destroy()

    def setup_ui(self):
        top_bar = tk.Frame(self, bg=THEME["card_bg"], padx=14, pady=10, highlightbackground=THEME["card_border"], highlightthickness=1)
        top_bar.pack(fill="x")
        
        self.ep_counter_lbl = tk.Label(top_bar, text="Episode 1 of 1", bg=THEME["card_bg"], fg=THEME["accent_cyan"], font=("Arial", 11, "bold"))
        self.ep_counter_lbl.pack(side="left")

        thumb_card = tk.Frame(self, bg=THEME["card_bg"], highlightbackground=THEME["card_border"], highlightthickness=1, padx=12, pady=12)
        thumb_card.pack(fill="both", expand=True, padx=14, pady=10)

        self.thumb_canvas = tk.Canvas(thumb_card, bg="#000000", highlightthickness=0, height=280)
        self.thumb_canvas.pack(fill="both", expand=True)

        self.title_lbl = tk.Label(thumb_card, text="", bg=THEME["card_bg"], fg=THEME["text_primary"], font=("Arial", 10, "bold"), wraplength=480, justify="center")
        self.title_lbl.pack(fill="x", pady=(8, 2))

        self.meta_lbl = tk.Label(thumb_card, text="", bg=THEME["card_bg"], fg=THEME["text_secondary"], font=("Arial", 9))
        self.meta_lbl.pack(fill="x", pady=(0, 4))

        btn_card = tk.Frame(self, bg=THEME["card_bg"], padx=14, pady=10, highlightbackground=THEME["card_border"], highlightthickness=1)
        btn_card.pack(fill="x", side="bottom")

        nav_box = tk.Frame(btn_card, bg=THEME["card_bg"])
        nav_box.pack(fill="x", pady=(0, 8))

        self.prev_btn = ttk.Button(nav_box, text="⏮ Prev Episode", command=self.prev_episode, style="DarkBtn.TButton")
        self.prev_btn.pack(side="left", padx=4)

        self.play_btn = ttk.Button(nav_box, text="▶ Play Video", command=self.play_video, style="PrimaryBtn.TButton")
        self.play_btn.pack(side="left", fill="x", expand=True, padx=4)

        self.next_btn = ttk.Button(nav_box, text="Next Episode ⏭", command=self.next_episode, style="DarkBtn.TButton")
        self.next_btn.pack(side="right", padx=4)

        open_box = tk.Frame(btn_card, bg=THEME["card_bg"])
        open_box.pack(fill="x")
        ttk.Button(open_box, text="📂 Show in Folder", command=self.show_in_folder, style="DarkBtn.TButton").pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(open_box, text="Close", command=self.destroy, style="DarkBtn.TButton").pack(side="right", padx=4)

    def display_episode(self):
        if not self.episodes:
            self.title_lbl.config(text="No completed downloads available to preview.")
            return

        item = self.episodes[self.idx]
        total = len(self.episodes)
        self.ep_counter_lbl.config(text=f"Episode {item.get('idx', self.idx + 1)} of {total}")
        self.title_lbl.config(text=item.get("title") or item.get("filename", "Video Preview"))
        
        file_size_mb = 0
        if os.path.exists(item.get("filepath", "")):
            file_size_mb = os.path.getsize(item["filepath"]) / (1024 * 1024)

        author_str = f"Author: {item.get('author')}" if item.get('author') else ""
        size_str = f"Size: {file_size_mb:.2f} MB" if file_size_mb > 0 else ""
        meta_text = " | ".join([p for p in [author_str, size_str, item.get("filename", "")] if p])
        self.meta_lbl.config(text=meta_text)

        cover_path = item.get("cover_path", "")
        self.thumb_canvas.delete("all")
        
        if cover_path and os.path.exists(cover_path):
            try:
                with Image.open(cover_path) as raw_img:
                    img = raw_img.copy()
                canvas_w = 480
                canvas_h = 280
                img.thumbnail((canvas_w, canvas_h), Image.Resampling.LANCZOS)
                self.photo_ref = ImageTk.PhotoImage(img)
                self.thumb_canvas.create_image(canvas_w / 2, canvas_h / 2, image=self.photo_ref, anchor="center")
            except Exception:
                self.thumb_canvas.create_text(240, 140, text="🖼️ [Thumbnail Loaded]", fill=THEME["text_secondary"], font=("Arial", 11))
        else:
            self.thumb_canvas.create_text(240, 140, text="🎬 [Video Ready to Play]", fill=THEME["accent_cyan"], font=("Arial", 12, "bold"))

        self.prev_btn.config(state="normal" if self.idx > 0 else "disabled")
        self.next_btn.config(state="normal" if self.idx < total - 1 else "disabled")

    def prev_episode(self):
        if self.idx > 0:
            self.idx -= 1
            self.display_episode()

    def next_episode(self):
        if self.idx < len(self.episodes) - 1:
            self.idx += 1
            self.display_episode()

    def play_video(self):
        if not self.episodes:
            return
        filepath = self.episodes[self.idx].get("filepath", "")
        if os.path.exists(filepath):
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", filepath])
            else:
                subprocess.Popen(["xdg-open", filepath])
        else:
            messagebox.showwarning("File Missing", f"Video file not found at: {filepath}")

    def show_in_folder(self):
        if not self.episodes:
            return
        filepath = self.episodes[self.idx].get("filepath", "")
        folder = os.path.dirname(filepath) if filepath else ""
        if folder and os.path.exists(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])


# ----------------- URL Normalization Helper -----------------
def normalize_tiktok_url(url):
    """
    Normalizes a TikTok video URL to match unique video items even if tracking query parameters differ.
    Supports standard /video/ID, mobile /v/ID.html, and standalone video IDs.
    """
    if not url or not isinstance(url, str):
        return ""
    clean = url.strip()
    m = re.search(r'(?:/video/|/v/|item_id=)(\d{15,22})', clean)
    if not m:
        m = re.search(r'(\d{18,20})', clean)
    if m:
        return f"tt_video_{m.group(1)}"
    return clean.split("?")[0].rstrip("/").lower()


# ----------------- Video Verification Helper -----------------
def verify_video_file(filepath, expected_size=None):
    """
    Dual-layer video integrity verification:
    1. Fast binary header/atom inspection (ftyp/moov check & minimum size)
    2. Deep ffprobe stream & codec validation
    Returns (is_valid: bool, reason: str)
    """
    if not os.path.exists(filepath):
        return False, "File not found on disk"

    actual_size = os.path.getsize(filepath)
    if actual_size < 30 * 1024:  # Under 30KB is considered corrupt/truncated
        return False, f"File too small ({actual_size} bytes)"

    if expected_size and expected_size > 0:
        if actual_size < expected_size * 0.95:
            return False, f"Truncated stream ({actual_size}/{expected_size} bytes)"

    # Layer 1: Check MP4 Atom Signatures
    try:
        with open(filepath, "rb") as f:
            header = f.read(128)
            if b"ftyp" not in header and b"moov" not in header:
                return False, "Missing valid MP4 container header (ftyp/moov atom missing)"
    except Exception as e:
        return False, f"File read error: {e}"

    # Layer 2: Deep ffprobe codec & stream validation (if ffprobe installed)
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,duration", "-of", "json", filepath]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
        if res.returncode == 0:
            info = json.loads(res.stdout.decode("utf-8"))
            streams = info.get("streams", [])
            if not streams:
                return False, "No valid video stream track found in file"
        else:
            err_msg = res.stderr.decode("utf-8").strip()
            if "Invalid data found" in err_msg or "moov atom not found" in err_msg:
                return False, f"Corrupted stream: {err_msg}"
    except (FileNotFoundError, Exception):
        pass

    return True, "Valid"


# ----------------- Main Desktop Application -----------------
class TikTokDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TikTok Drama & Video Batch Downloader Pro")
        self.root.geometry("860x800")
        self.root.minsize(740, 640)
        self.root.configure(bg=THEME["bg"])

        self.is_downloading = False
        self.should_stop = False
        self.active_workers = []
        self.download_queue = queue.Queue()
        self.failed_items = []
        self.completed_items_info = []
        self.lock = threading.Lock()

        # Queue Data: list of dicts { 'idx': 1, 'selected': True, 'title': '...', 'status': 'Pending', 'size': '--', 'url': '...', 'filepath': '...', 'cover_path': '...' }
        self.queue_items = []

        # Metrics tracking
        self.total_bytes_downloaded = 0
        self.start_time = 0
        self.processed_count = 0
        self.success_count = 0
        self.total_count = 0

        # State Variables
        self.base_save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "TikTok_Downloads")
        self.save_dir_var = tk.StringVar(value=self.base_save_dir)
        self.save_dir_var.trace_add("write", lambda *args: self.on_save_dir_changed())
        self.delay_var = tk.DoubleVar(value=1.0)
        self.threads_var = tk.IntVar(value=3)
        self.prefix_var = tk.StringVar(value="TikTok_Drama_Ep_")
        self.prefix_var.trace_add("write", lambda *args: self.on_prefix_changed())
        
        self.skip_existing_var = tk.BooleanVar(value=True)
        self.save_thumbnails_var = tk.BooleanVar(value=True)

        self.setup_styles()
        self.setup_ui()
        self.root.after(150, self.start_local_bridge)
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)
        self.log("💡 Tip: Click '🌐 Browser Setup Helper' on TikTok, or press Ctrl+V / '+ Add Links...' to load drama episodes.", tag="info")

    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=THEME["bg"], foreground=THEME["text_primary"], font=("Arial", 9))
        style.configure("Card.TFrame", background=THEME["card_bg"], relief="flat")
        style.configure("Dark.TEntry", fieldbackground=THEME["input_bg"], foreground=THEME["input_fg"], insertcolor=THEME["accent_cyan"], bordercolor=THEME["card_border"], lightcolor=THEME["card_border"], darkcolor=THEME["card_border"])
        style.configure("Dark.TSpinbox", fieldbackground=THEME["input_bg"], foreground=THEME["input_fg"], bordercolor=THEME["card_border"], arrowsize=10)
        style.configure("Dark.TCheckbutton", background=THEME["card_bg"], foreground=THEME["text_primary"], focuscolor=THEME["card_bg"])



        style.configure("DarkBtn.TButton", background=THEME["btn_dark_bg"], foreground=THEME["text_primary"], borderwidth=1, bordercolor=THEME["card_border"], focusthickness=0, padding=5)
        style.map("DarkBtn.TButton", background=[("active", THEME["btn_dark_hover"]), ("disabled", THEME["card_bg"])], foreground=[("disabled", "#4b5563")])

        style.configure("PrimaryBtn.TButton", background=THEME["accent_cyan"], foreground="#090d16", font=("Arial", 10, "bold"), borderwidth=0, padding=8)
        style.map("PrimaryBtn.TButton", background=[("active", "#0891b2"), ("disabled", "#1e293b")], foreground=[("disabled", "#64748b")])

        style.configure("DangerBtn.TButton", background=THEME["accent_rose"], foreground="#ffffff", font=("Arial", 9, "bold"), borderwidth=0, padding=8)
        style.map("DangerBtn.TButton", background=[("active", "#be123c"), ("disabled", "#1e293b")], foreground=[("disabled", "#64748b")])

        style.configure("AmberBtn.TButton", background=THEME["accent_amber"], foreground="#ffffff", font=("Arial", 9, "bold"), borderwidth=0, padding=5)
        style.map("AmberBtn.TButton", background=[("active", "#b45309"), ("disabled", "#1e293b")], foreground=[("disabled", "#64748b")])

        style.configure("PurpleBtn.TButton", background=THEME["accent_purple"], foreground="#ffffff", font=("Arial", 9, "bold"), borderwidth=0, padding=6)
        style.map("PurpleBtn.TButton", background=[("active", "#9333ea"), ("disabled", "#1e293b")], foreground=[("disabled", "#64748b")])

        # Dark Treeview Styling
        style.configure("Dark.Treeview", background=THEME["input_bg"], foreground=THEME["input_fg"], fieldbackground=THEME["input_bg"], borderwidth=0, rowheight=26, font=("Arial", 9))
        style.configure("Dark.Treeview.Heading", background=THEME["card_bg"], foreground=THEME["accent_cyan"], font=("Arial", 9, "bold"), relief="flat", padding=4)
        style.map("Dark.Treeview.Heading", background=[("active", THEME["btn_dark_hover"])])
        style.map("Dark.Treeview", background=[("selected", "#0369a1")], foreground=[("selected", "#ffffff")])

    def create_card(self, parent, title):
        card = tk.Frame(parent, bg=THEME["card_bg"], highlightbackground=THEME["card_border"], highlightthickness=1, padx=10, pady=6)
        card.pack(fill="x", padx=14, pady=3)
        if title:
            header_box = tk.Frame(card, bg=THEME["card_bg"])
            header_box.pack(fill="x", pady=(0, 3))
            tk.Label(header_box, text=title, bg=THEME["card_bg"], fg=THEME["accent_cyan"], font=("Arial", 9, "bold")).pack(side="left")
        return card

    def setup_ui(self):
        # 1. Header Banner
        header = tk.Frame(self.root, bg=THEME["bg"], padx=14, pady=8)
        header.pack(fill="x")
        
        tk.Label(header, text="🎬 TikTok Downloader Pro", bg=THEME["bg"], fg="#ffffff", font=("Arial", 12, "bold")).pack(side="left")
        self.bridge_badge = tk.Label(header, text="🟢 Local Bridge Online (54321)", bg="#064e3b", fg="#34d399", font=("Arial", 8, "bold"), padx=8, pady=3)
        self.bridge_badge.pack(side="right")
        
        ttk.Button(header, text="🌐 Browser Setup Helper", command=self.open_browser_setup, style="DarkBtn.TButton").pack(side="right", padx=(0, 8))

        # 2. Interactive Video Queue Table Card (EXPANDS to dominate majority of window)
        queue_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["card_border"], highlightthickness=1, padx=10, pady=8)
        queue_card.pack(fill="both", expand=True, padx=14, pady=(0, 4))

        # Toolbar above table
        toolbar = tk.Frame(queue_card, bg=THEME["card_bg"])
        toolbar.pack(fill="x", pady=(0, 6))

        ttk.Button(toolbar, text="➕ Add Links...", command=self.open_add_links_modal, style="PrimaryBtn.TButton").pack(side="left", padx=(0, 4))
        self.toggle_select_btn = ttk.Button(toolbar, text="☑ Select All", command=self.toggle_select_all_items, style="DarkBtn.TButton")
        self.toggle_select_btn.pack(side="left", padx=2)
        ttk.Button(toolbar, text="🧹 Clear", command=self.clear_all_items, style="DarkBtn.TButton").pack(side="left", padx=2)
        
        self.count_badge = tk.Label(toolbar, text="0 / 0 Selected", bg="#1e293b", fg=THEME["accent_cyan"], font=("Arial", 9, "bold"), padx=10, pady=2)
        self.count_badge.pack(side="right")

        # Treeview Container
        tree_container = tk.Frame(queue_card, bg=THEME["input_bg"], highlightbackground=THEME["card_border"], highlightthickness=1)
        tree_container.pack(fill="both", expand=True)

        columns = ("select", "ep", "title", "status", "size", "url", "action")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", style="Dark.Treeview", selectmode="extended")

        self.tree.heading("select", text="[X]", command=self.toggle_select_all_items)
        self.tree.heading("ep", text="#")
        self.tree.heading("title", text="Video Title / Episode")
        self.tree.heading("status", text="Download Status")
        self.tree.heading("size", text="Size")
        self.tree.heading("url", text="TikTok Link")
        self.tree.heading("action", text="Action")

        self.tree.column("select", width=45, anchor="center", stretch=False)
        self.tree.column("ep", width=55, anchor="center", stretch=False)
        self.tree.column("title", minwidth=220, width=280, anchor="w", stretch=True)
        self.tree.column("status", width=125, anchor="w", stretch=False)
        self.tree.column("size", width=75, anchor="center", stretch=False)
        self.tree.column("url", width=125, anchor="center", stretch=False)
        self.tree.column("action", width=85, anchor="center", stretch=False)

        tree_scroll_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set)

        tree_scroll_y.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # Tree Events: Click to toggle checkbox / open link / retry, Double-click to preview or download, Right-click context menu
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.show_tree_context_menu)
        self.tree.bind("<space>", lambda e: self.toggle_selected_rows())

        # Global Pro Keyboard Shortcuts
        self.root.bind("<Control-v>", lambda e: self.quick_paste_add_modal())
        self.root.bind("<Control-V>", lambda e: self.quick_paste_add_modal())
        self.root.bind("<Control-Return>", lambda e: self.toggle_download_state())
        self.root.bind("<Control-o>", lambda e: self.open_save_folder())
        self.root.bind("<Control-O>", lambda e: self.open_save_folder())
        self.root.bind("<Control-a>", lambda e: self.toggle_select_all_items())
        self.root.bind("<Control-A>", lambda e: self.toggle_select_all_items())
        self.tree.bind("<Delete>", lambda e: self.remove_selected_items())
        self.tree.bind("<BackSpace>", lambda e: self.remove_selected_items())

        # Context Menu
        self.tree_menu = tk.Menu(self.root, tearoff=0, bg=THEME["card_bg"], fg=THEME["text_primary"], activebackground="#0284c7", activeforeground="#ffffff", font=("Arial", 9))
        self.tree_menu.add_command(label="▶ Preview / Play Video", command=self.context_preview_video)
        self.tree_menu.add_command(label="🔁 Retry Download This Item", command=self.context_retry_item)
        self.tree_menu.add_command(label="🌐 Open TikTok Link in Browser ↗", command=self.context_open_url)
        self.tree_menu.add_command(label="📂 Show in Folder", command=self.context_show_in_folder)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="✏️ Rename Series Title / Prefix...", command=self.rename_series_title)
        self.tree_menu.add_command(label="☑ Toggle Selection (Space)", command=self.toggle_selected_rows)
        self.tree_menu.add_command(label="📋 Copy TikTok URL", command=self.context_copy_url)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="💾 Export Queue (.json)...", command=self.export_queue)
        self.tree_menu.add_command(label="📂 Import Queue / File...", command=self.import_queue)
        self.tree_menu.add_command(label="🗑️ Remove from Queue", command=self.remove_selected_items)

        # 3. Unified Minimalist Control Bar (Folder + Settings consolidated in 1 line)
        ctrl_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["card_border"], highlightthickness=1, padx=10, pady=5)
        ctrl_card.pack(fill="x", padx=14, pady=2)

        tk.Label(ctrl_card, text="📂", bg=THEME["card_bg"], fg=THEME["accent_cyan"], font=("Arial", 9)).pack(side="left")
        self.folder_entry = ttk.Entry(ctrl_card, textvariable=self.save_dir_var, style="Dark.TEntry")
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(4, 6))
        ttk.Button(ctrl_card, text="Browse", command=self.browse_folder, style="DarkBtn.TButton").pack(side="left", padx=2)
        ttk.Button(ctrl_card, text="Open", command=self.open_save_folder, style="DarkBtn.TButton").pack(side="left", padx=2)

        tk.Label(ctrl_card, text="⚙️ Threads:", bg=THEME["card_bg"], fg=THEME["text_secondary"], font=("Arial", 9)).pack(side="left", padx=(10, 2))
        ttk.Spinbox(ctrl_card, from_=1, to=5, textvariable=self.threads_var, width=2, style="Dark.TSpinbox").pack(side="left", padx=2)

        ttk.Checkbutton(ctrl_card, text="Skip Existing", variable=self.skip_existing_var, style="Dark.TCheckbutton").pack(side="left", padx=(8, 2))
        ttk.Checkbutton(ctrl_card, text="Posters", variable=self.save_thumbnails_var, style="Dark.TCheckbutton").pack(side="left", padx=2)

        # 4. Main Action & Integrated Progress Card
        action_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["card_border"], highlightthickness=1, padx=10, pady=6)
        action_card.pack(fill="x", padx=14, pady=2)

        self.toggle_download_btn = ttk.Button(action_card, text="▶ Start Batch Download", command=self.toggle_download_state, style="PrimaryBtn.TButton")
        self.toggle_download_btn.pack(fill="x", expand=True, pady=(0, 4))

        self.progress_bar = ModernProgressBar(action_card, height=18)
        self.progress_bar.pack(fill="x")

        self.metrics_label = tk.Label(action_card, text="Status: Ready to start...", bg=THEME["card_bg"], fg=THEME["text_secondary"], font=("Arial", 8), anchor="center")
        self.metrics_label.pack(fill="x", pady=(2, 0))

        # 5. Compact Minimal Activity Logs
        log_card = tk.Frame(self.root, bg=THEME["card_bg"], highlightbackground=THEME["card_border"], highlightthickness=1, padx=10, pady=4)
        log_card.pack(fill="x", padx=14, pady=(2, 8))

        log_head = tk.Frame(log_card, bg=THEME["card_bg"])
        log_head.pack(fill="x", pady=(0, 2))
        tk.Label(log_head, text="📜 Activity", bg=THEME["card_bg"], fg=THEME["accent_cyan"], font=("Arial", 8, "bold")).pack(side="left")

        ttk.Button(log_head, text="Clear", command=self.clear_logs, style="DarkBtn.TButton").pack(side="right", padx=1)
        ttk.Button(log_head, text="Save", command=self.save_logs, style="DarkBtn.TButton").pack(side="right", padx=1)
        self.copy_failed_btn = ttk.Button(log_head, text="📋 Copy Failed", command=self.copy_failed_links, state="disabled", style="DarkBtn.TButton").pack(side="right", padx=1)

        log_container = tk.Frame(log_card, bg=THEME["log_bg"], highlightbackground=THEME["card_border"], highlightthickness=1)
        log_container.pack(fill="x", expand=True)

        self.log_text = tk.Text(log_container, height=2, wrap="word", state="disabled", font=("Consolas", 8), bg=THEME["log_bg"], fg="#f4f4f5", relief="flat", padx=4, pady=2)
        log_scroll = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_text.tag_config("success", foreground=THEME["accent_emerald"])
        self.log_text.tag_config("error", foreground=THEME["accent_rose"], font=("Consolas", 8, "bold"))
        self.log_text.tag_config("warn", foreground=THEME["accent_amber"])
        self.log_text.tag_config("info", foreground=THEME["accent_cyan"])
        self.log_text.tag_config("skip", foreground=THEME["accent_purple"])

    # ----------------- Queue Table Management -----------------
    def on_save_dir_changed(self):
        save_dir = self.save_dir_var.get().strip()
        for it in self.queue_items:
            if it["status"] in ["Pending", ""]:
                it["filepath"] = os.path.join(save_dir, it["filename"])
                it["cover_path"] = os.path.join(save_dir, f"{os.path.splitext(it['filename'])[0]}.jpg")

    def on_prefix_changed(self):
        prefix = self.prefix_var.get().strip()
        save_dir = self.save_dir_var.get().strip()
        for it in self.queue_items:
            if it["status"] in ["Pending", ""]:
                it["filename"] = f"{prefix}{it['ep_str']}.mp4"
                it["title"] = it["filename"]
                it["filepath"] = os.path.join(save_dir, it["filename"])
                it["cover_path"] = os.path.join(save_dir, f"{prefix}{it['ep_str']}.jpg")
                if self.tree.exists(str(it["idx"])):
                    self.tree.set(str(it["idx"]), column="title", value=it["title"])

    def rename_series_title(self):
        curr = self.prefix_var.get().strip()
        new_val = simpledialog.askstring("Rename Series Title", "Enter new Series Drama Title / Prefix:", initialvalue=curr, parent=self.root)
        if new_val is not None and new_val.strip():
            raw_name = new_val.strip()
            clean = re.sub(r'[\\/:*?"<>|]', '_', raw_name)
            folder_name = clean.replace("_Ep_", "").replace("_", " ").strip()
            if not clean.endswith("_Ep_") and not clean.endswith("_"):
                clean += "_Ep_"
            if folder_name:
                self.save_dir_var.set(os.path.join(self.base_save_dir, folder_name))
            self.prefix_var.set(clean)
            self.log(f"✏️ Renamed Series Title to: '{folder_name}' | Folder: {self.save_dir_var.get()}", tag="info")

    def export_queue(self):
        if not self.queue_items:
            messagebox.showinfo("Empty Queue", "There are no items in the queue to export.")
            return
        fpath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if fpath:
            data = {
                "series_title": self.prefix_var.get().replace("_Ep_", "").replace("_", " ").strip(),
                "prefix": self.prefix_var.get(),
                "save_dir": self.save_dir_var.get(),
                "episodes": [
                    {"episode": it.get("ep_str"), "url": it.get("url"), "title": it.get("title")}
                    for it in self.queue_items
                ]
            }
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.log(f"💾 Exported {len(self.queue_items)} episode(s) to {os.path.basename(fpath)}", tag="info")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(self.queue_items)} episode(s).")

    def import_queue(self):
        fpath = filedialog.askopenfilename(filetypes=[("JSON Queue Files", "*.json"), ("Text Files", "*.txt"), ("All Files", "*.*")])
        if fpath:
            try:
                if fpath.endswith(".json"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        if "prefix" in data:
                            self.prefix_var.set(data["prefix"])
                        if "save_dir" in data:
                            self.save_dir_var.set(data["save_dir"])
                        items = data.get("episodes") or data.get("items") or data.get("urls", [])
                        series_title = data.get("series_title", "")
                        self.load_urls_into_queue(items, series_title=series_title)
                    elif isinstance(data, list):
                        self.load_urls_into_queue(data)
                else:
                    with open(fpath, "r", encoding="utf-8") as f:
                        urls = [line.strip() for line in f if line.strip().startswith("http")]
                    self.load_urls_into_queue(urls)
                self.log(f"📂 Imported queue from {os.path.basename(fpath)}", tag="info")
            except Exception as ex:
                messagebox.showerror("Import Error", f"Failed to import queue: {ex}")

    def open_add_links_modal(self):
        AddLinksModal(self.root, self.load_urls_into_queue)

    def quick_paste_add_modal(self):
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text)):
            return
        AddLinksModal(self.root, self.load_urls_into_queue, auto_paste=True)

    def load_urls_into_queue(self, items, series_title=""):
        if not items:
            return
        
        # 1. Normalize items into a uniform structure: [{"episode": int/None, "url": str}]
        parsed_entries = []
        for it in items:
            if isinstance(it, dict):
                url = it.get("url", "").strip()
                ep_num = it.get("episode")
                if url:
                    parsed_entries.append({"episode": ep_num, "url": url})
            elif isinstance(it, str):
                url = it.strip()
                if url and url.startswith("http"):
                    parsed_entries.append({"episode": None, "url": url})

        if not parsed_entries:
            return

        # 2. Deduplicate incoming list and filter against existing queue items
        existing_normalized = {normalize_tiktok_url(q["url"]) for q in self.queue_items}
        
        unique_entries = []
        seen_new = set()
        for entry in parsed_entries:
            norm = normalize_tiktok_url(entry["url"])
            if norm and norm not in existing_normalized and norm not in seen_new:
                seen_new.add(norm)
                unique_entries.append(entry)

        duplicate_count = len(parsed_entries) - len(unique_entries)

        if not unique_entries:
            self.log(f"⚠️ Duplicate Check: All {len(parsed_entries)} episode link(s) are already in the download queue. Skipped.", tag="warn")
            return

        if series_title:
            raw_title = series_title.strip()
            clean_folder = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', raw_title).strip()
            clean_prefix = clean_folder
            if not clean_prefix.endswith("_Ep_") and not clean_prefix.endswith("_"):
                clean_prefix += "_Ep_"
            
            # Automatically set dedicated subfolder for this drama series!
            target_subfolder = os.path.join(self.base_save_dir, clean_folder)
            self.save_dir_var.set(target_subfolder)
            self.prefix_var.set(clean_prefix)
            self.log(f"🎬 Drama Series: '{raw_title}' -> Folder: {target_subfolder}", tag="info")

        prefix = self.prefix_var.get().strip()
        max_current_idx = max([it["idx"] for it in self.queue_items], default=0)

        # Calculate padding based on max episode number
        max_ep_val = 0
        for entry in unique_entries:
            if entry.get("episode") is not None:
                try:
                    max_ep_val = max(max_ep_val, int(entry["episode"]))
                except Exception:
                    pass
        total_projected = max(max_ep_val, len(self.queue_items) + len(unique_entries))
        padding = max(2, len(str(total_projected)))

        new_items = []
        for i, entry in enumerate(unique_entries, max_current_idx + 1):
            if entry.get("episode") is not None:
                try:
                    ep_val = int(entry["episode"])
                    ep_str = str(ep_val).zfill(padding)
                except Exception:
                    ep_str = str(i).zfill(padding)
            else:
                ep_str = str(i).zfill(padding)

            fname = f"{prefix}{ep_str}.mp4"
            item = {
                "idx": i,
                "selected": True,
                "ep_str": ep_str,
                "title": fname,
                "status": "Pending",
                "size": "--",
                "url": entry["url"],
                "filename": fname,
                "filepath": os.path.join(self.save_dir_var.get().strip(), fname),
                "cover_path": os.path.join(self.save_dir_var.get().strip(), f"{prefix}{ep_str}.jpg")
            }
            new_items.append(item)

        self.queue_items.extend(new_items)
        self.refresh_tree()
        
        if duplicate_count > 0:
            self.log(f"📥 Added {len(unique_entries)} new episode(s) (Skipped {duplicate_count} duplicate link(s)).", tag="info")
        else:
            self.log(f"📥 Added {len(unique_entries)} episode(s) to download queue.", tag="info")

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for item in self.queue_items:
            chk = "☑" if item["selected"] else "☐"
            ep_display = f"Ep {item['ep_str']}"
            self.tree.insert("", "end", iid=str(item["idx"]), values=(
                chk,
                ep_display,
                item["title"],
                item["status"],
                item["size"],
                "🌐 Open Link ↗",
                "🔁 Retry"
            ))
        self.update_selection_counter()

    def update_selection_counter(self):
        sel_count = sum(1 for it in self.queue_items if it["selected"])
        total_count = len(self.queue_items)
        self.count_badge.config(text=f"{sel_count} / {total_count} Selected")
        if hasattr(self, "toggle_select_btn"):
            if total_count > 0 and sel_count == total_count:
                self.toggle_select_btn.config(text="☐ Deselect All")
            else:
                self.toggle_select_btn.config(text="☑ Select All")

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            if item_id:
                idx = int(item_id)
                target_item = next((it for it in self.queue_items if it["idx"] == idx), None)
                if not target_item:
                    return

                if col == "#1":  # select column
                    target_item["selected"] = not target_item["selected"]
                    chk = "☑" if target_item["selected"] else "☐"
                    self.tree.set(item_id, column="select", value=chk)
                    self.update_selection_counter()
                elif col == "#6":  # url column -> open link in browser
                    url = target_item.get("url")
                    if url:
                        webbrowser.open(url)
                        self.log(f"🌐 Opened TikTok in Browser: {url}", tag="info")
                elif col == "#7":  # action column -> retry this item
                    self.retry_single_item(idx)

    def toggle_selected_rows(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            return
        for iid in selected_iids:
            idx = int(iid)
            for it in self.queue_items:
                if it["idx"] == idx:
                    it["selected"] = not it["selected"]
                    chk = "☑" if it["selected"] else "☐"
                    self.tree.set(iid, column="select", value=chk)
                    break
        self.update_selection_counter()

    def show_tree_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            if item_id not in self.tree.selection():
                self.tree.selection_set(item_id)
            self.tree_menu.tk_popup(event.x_root, event.y_root)

    def context_preview_video(self):
        selected = self.tree.selection()
        if selected:
            idx = int(selected[0])
            self.launch_preview_for_idx(idx)

    def context_retry_item(self):
        selected = self.tree.selection()
        if selected:
            idx = int(selected[0])
            self.retry_single_item(idx)

    def context_open_url(self):
        selected = self.tree.selection()
        if selected:
            idx = int(selected[0])
            target_item = next((it for it in self.queue_items if it["idx"] == idx), None)
            if target_item and target_item.get("url"):
                webbrowser.open(target_item["url"])
                self.log(f"🌐 Opened TikTok in Browser: {target_item['url']}", tag="info")

    def retry_single_item(self, idx):
        target_item = next((it for it in self.queue_items if it["idx"] == idx), None)
        if not target_item:
            return
        if self.is_downloading:
            messagebox.showinfo("Download in Progress", "Please wait for current batch or click Stop before retrying a single item.")
            return

        save_dir = self.save_dir_var.get().strip()
        target_item["status"] = "Pending"
        self.update_row_in_tree(idx, status="Pending")
        self.log(f"🔁 Retrying download for Episode {target_item.get('ep_str', idx)}...", tag="info")
        self.run_batch_job([target_item], save_dir, 1)

    def context_show_in_folder(self):
        selected = self.tree.selection()
        if selected:
            idx = int(selected[0])
            target_item = next((it for it in self.queue_items if it["idx"] == idx), None)
            if target_item and os.path.exists(target_item.get("filepath", "")):
                folder = os.path.dirname(target_item["filepath"])
                if sys.platform == "win32":
                    os.startfile(folder)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
            else:
                self.open_save_folder()

    def context_copy_url(self):
        selected = self.tree.selection()
        if selected:
            urls = []
            for iid in selected:
                idx = int(iid)
                target_item = next((it for it in self.queue_items if it["idx"] == idx), None)
                if target_item:
                    urls.append(target_item["url"])
            if urls:
                self.root.clipboard_clear()
                self.root.clipboard_append("\n".join(urls))

    def on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            idx = int(item_id)
            target_item = next((it for it in self.queue_items if it["idx"] == idx), None)
            if target_item:
                filepath = target_item.get("filepath", "")
                if os.path.exists(filepath):
                    self.launch_preview_for_idx(idx)
                else:
                    self.retry_single_item(idx)

    def launch_preview_for_idx(self, idx):
        target_item = next((it for it in self.queue_items if it["idx"] == idx), None)
        if target_item and os.path.exists(target_item.get("filepath", "")):
            preview_list = [it for it in self.queue_items if os.path.exists(it.get("filepath", ""))]
            cur_idx = 0
            for i, it in enumerate(preview_list):
                if it["idx"] == idx:
                    cur_idx = i
                    break
            VideoPreviewModal(self.root, preview_list, cur_idx)
        else:
            messagebox.showinfo("Not Downloaded", "This video has not been downloaded yet. Please download it first to preview.")

    def toggle_select_all_items(self):
        if not self.queue_items:
            return
        all_selected = all(it["selected"] for it in self.queue_items)
        new_state = not all_selected
        for it in self.queue_items:
            it["selected"] = new_state
        self.refresh_tree()

    def remove_selected_items(self):
        self.queue_items = [it for it in self.queue_items if not it["selected"]]
        self.refresh_tree()

    def clear_all_items(self):
        self.queue_items = []
        self.refresh_tree()

    # ----------------- Local Bridge Handlers -----------------
    def open_browser_setup(self):
        try:
            webbrowser.open(f"http://{BRIDGE_HOST}:{BRIDGE_PORT}/setup")
        except Exception:
            pass

    def start_local_bridge(self):
        def run_server():
            try:
                server = ReusableHTTPServer((BRIDGE_HOST, BRIDGE_PORT), BridgeRequestHandler)
                server.app = self
                self.bridge_server = server
                self.log(f"🟢 Local HTTP Bridge listening on http://{BRIDGE_HOST}:{BRIDGE_PORT}", tag="info")
                server.serve_forever()
            except Exception as e:
                self.root.after(0, lambda: self.bridge_badge.config(text="🔴 Bridge Offline", bg="#7f1d1d", fg="#fca5a5"))
                self.log(f"⚠️ Local Bridge port {BRIDGE_PORT} conflict: {e}", tag="warn")

        bridge_thread = threading.Thread(target=run_server, daemon=True)
        bridge_thread.start()

    def bring_window_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(300, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    def on_links_received_from_bridge(self, items, series_title=""):
        if not items:
            return
        
        self.bring_window_to_front()
        self.load_urls_into_queue(items, series_title=series_title)
        self.log(f"📥 Received {len(items)} episode(s) from Browser Bridge!", tag="info")

    # ----------------- UI Helpers & Logging -----------------
    def log(self, message, tag=None):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.root.after(0, lambda m=message, t=tag: self.log(m, t))
            except Exception:
                pass
            return

        self.log_text.configure(state="normal")
        
        # Memory Cap: Trim oldest lines if log exceeds 1,000 lines
        try:
            line_count = int(self.log_text.index('end-1c').split('.')[0])
            if line_count > 1000:
                self.log_text.delete("1.0", "100.0")
        except Exception:
            pass

        timestamp = time.strftime("[%H:%M:%S] ")
        if tag:
            self.log_text.insert("end", timestamp + message + "\n", tag)
        else:
            if "✅" in message:
                self.log_text.insert("end", timestamp + message + "\n", "success")
            elif "⏭️" in message or "Skipped" in message:
                self.log_text.insert("end", timestamp + message + "\n", "skip")
            elif "❌" in message or "Failed" in message or "Error" in message:
                self.log_text.insert("end", timestamp + message + "\n", "error")
            elif "⚠️" in message:
                self.log_text.insert("end", timestamp + message + "\n", "warn")
            else:
                self.log_text.insert("end", timestamp + message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_logs(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def save_logs(self):
        content = self.log_text.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo("Empty Logs", "There are no logs to save.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Saved", f"Logs successfully saved to {os.path.basename(file_path)}")

    def browse_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.save_dir_var.get())
        if chosen:
            self.save_dir_var.set(chosen)
            self.base_save_dir = chosen

    def open_save_folder(self):
        folder = self.save_dir_var.get().strip()
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def copy_failed_links(self):
        if not self.failed_items:
            return
        failed_urls = [item["url"] for item in self.failed_items]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(failed_urls))
        messagebox.showinfo("Copied", f"Copied {len(failed_urls)} failed links to clipboard!")

    def open_preview_player(self):
        preview_list = [it for it in self.queue_items if os.path.exists(it.get("filepath", ""))]
        
        if not preview_list:
            save_dir = self.save_dir_var.get().strip()
            if os.path.exists(save_dir):
                files = sorted([f for f in os.listdir(save_dir) if f.endswith(".mp4")])
                for idx, fname in enumerate(files, 1):
                    fpath = os.path.join(save_dir, fname)
                    cpath = os.path.splitext(fpath)[0] + ".jpg"
                    preview_list.append({
                        "idx": idx,
                        "filename": fname,
                        "filepath": fpath,
                        "cover_path": cpath if os.path.exists(cpath) else "",
                        "title": fname,
                        "author": "TikTok Drama"
                    })

        if not preview_list:
            messagebox.showinfo("No Videos Yet", "No downloaded videos found to preview. Please download episodes first.")
            return

        VideoPreviewModal(self.root, preview_list)

    # ----------------- Download Engine & Worker Pool -----------------
    def toggle_download_state(self):
        if self.is_downloading:
            self.stop_download()
        else:
            self.start_download()

    def start_download(self):
        selected_items = [it for it in self.queue_items if it["selected"]]
        if not selected_items:
            messagebox.showwarning("No Items Selected", "Please select (check) at least one video in the queue to download.")
            return

        save_dir = self.save_dir_var.get().strip()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Directory Error", f"Cannot create folder: {e}")
                return

        # Update filepaths in selected items
        prefix = self.prefix_var.get().strip()
        for it in selected_items:
            it["filename"] = f"{prefix}{it['ep_str']}.mp4"
            it["filepath"] = os.path.join(save_dir, it["filename"])
            it["cover_path"] = os.path.join(save_dir, f"{prefix}{it['ep_str']}.jpg")
            it["status"] = "Pending"
            if self.tree.exists(str(it["idx"])):
                self.tree.set(str(it["idx"]), column="status", value="Pending")

        self.run_batch_job(selected_items, save_dir, len(selected_items))

    def run_batch_job(self, items, save_dir, total_count):
        self.is_downloading = True
        self.should_stop = False
        self.failed_items = []
        self.success_count = 0
        self.processed_count = 0
        self.total_count = total_count
        self.total_bytes_downloaded = 0
        self.start_time = time.time()

        self.toggle_download_btn.config(text="⏹ Stop Download", style="DangerBtn.TButton")
        self.progress_bar.set_progress(0, total_count, "0.0% (0/{})".format(total_count))

        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
            except Exception:
                break

        for it in items:
            self.download_queue.put(it)

        num_threads = min(self.threads_var.get(), total_count)
        self.active_workers = []
        self.log(f"🚀 Batch started: {total_count} video(s) using {num_threads} worker thread(s)...", tag="info")

        for t_id in range(num_threads):
            worker = threading.Thread(target=self.worker_thread_loop, args=(t_id + 1, save_dir), daemon=True)
            self.active_workers.append(worker)
            worker.start()

        supervisor = threading.Thread(target=self.supervisor_loop, daemon=True)
        supervisor.start()

    def update_row_in_tree(self, item_id, title=None, status=None, size=None):
        if self.tree.exists(str(item_id)):
            if title:
                self.tree.set(str(item_id), column="title", value=title)
            if status:
                self.tree.set(str(item_id), column="status", value=status)
            if size:
                self.tree.set(str(item_id), column="size", value=size)

    def worker_thread_loop(self, worker_id, save_dir):
        delay = self.delay_var.get()
        skip_existing = self.skip_existing_var.get()
        save_thumbnails = self.save_thumbnails_var.get()
        prefix = self.prefix_var.get().strip()
        worker_session = create_http_session(pool_size=6)

        while not self.should_stop:
            try:
                item = self.download_queue.get(timeout=0.5)
            except queue.Empty:
                break

            idx = item["idx"]
            url = item["url"]
            filename = item["filename"]
            ep_str = item.get("ep_str", str(idx).zfill(2))
            filepath = os.path.join(save_dir, filename)

            # 1. Smart Skip Check with Integrity Verification
            candidate_files = [
                filepath,
                os.path.join(save_dir, f"{item.get('title', '')}.mp4"),
                os.path.join(save_dir, f"{item.get('title', '')}")
            ]
            already_downloaded_path = None
            for c_path in candidate_files:
                if c_path and os.path.exists(c_path):
                    is_valid, reason = verify_video_file(c_path)
                    if is_valid:
                        already_downloaded_path = c_path
                        break
                    else:
                        try:
                            os.remove(c_path)
                        except Exception:
                            pass

            if skip_existing and already_downloaded_path:
                fsize_mb = os.path.getsize(already_downloaded_path) / (1024 * 1024)
                size_str = f"{fsize_mb:.1f} MB"
                final_fname = os.path.basename(already_downloaded_path)
                display_title = os.path.splitext(final_fname)[0]
                with self.lock:
                    self.processed_count += 1
                    self.success_count += 1
                    item["status"] = "⏭️ Skipped"
                    item["size"] = size_str
                    item["filename"] = final_fname
                    item["filepath"] = already_downloaded_path
                    item["title"] = display_title
                    self.root.after(0, self.update_row_in_tree, idx, display_title, "⏭️ Skipped", size_str)
                    self.root.after(0, self.log, f"⏭️ [T{worker_id}] Verified & Skipped Episode {idx}: {display_title} ({size_str})", "skip")
                    self.root.after(0, self.update_batch_progress)
                self.download_queue.task_done()
                continue

            self.root.after(0, self.update_row_in_tree, idx, None, "⚡ Downloading...", None)
            success = False
            last_err = ""
            meta_title = ""
            meta_author = ""
            final_filename = filename
            final_filepath = filepath
            downloaded_bytes = 0

            for attempt in range(1, MAX_AUTO_RETRIES + 1):
                if self.should_stop:
                    break

                if attempt > 1:
                    jitter_sleep = (1.2 * attempt) + random.uniform(0.2, 0.6)
                    self.root.after(0, self.log, f"🔄 [T{worker_id}] Retrying Episode {idx} in {jitter_sleep:.1f}s (Attempt {attempt}/{MAX_AUTO_RETRIES})...", "warn")
                    time.sleep(jitter_sleep)

                try:
                    meta_res = extract_tiktok_metadata(url, session=worker_session)
                    if not meta_res.get("success"):
                        last_err = meta_res.get("error", "Failed to extract video stream URL")
                        continue

                    video_url = meta_res["video_url"]
                    cover_url = meta_res.get("cover_url")
                    raw_title = meta_res.get("title", "").strip()
                    meta_author = meta_res.get("author", "TikTok Creator")

                    # Determine Clean Filename from Real Video Title
                    if raw_title:
                        clean_title = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', raw_title).strip()
                        clean_title = re.sub(r'\s+', ' ', clean_title)[:140].strip()
                        final_filename = f"{clean_title}.mp4"
                        meta_title = clean_title
                    else:
                        final_filename = filename
                        meta_title = os.path.splitext(filename)[0]

                    final_filepath = os.path.join(save_dir, final_filename)
                    final_coverpath = os.path.join(save_dir, f"{os.path.splitext(final_filename)[0]}.jpg")
                    part_filepath = f"{final_filepath}.part"

                    # Download poster cover
                    if save_thumbnails and cover_url:
                        try:
                            c_resp = worker_session.get(cover_url, timeout=(4, 12))
                            if c_resp.status_code == 200:
                                with open(final_coverpath, "wb") as cf:
                                    cf.write(c_resp.content)
                                poster_path = os.path.join(save_dir, f"{prefix}Poster.jpg")
                                if not os.path.exists(poster_path):
                                    with open(poster_path, "wb") as pf:
                                        pf.write(c_resp.content)
                        except Exception:
                            pass

                    # High-throughput 256KB stream buffering with CDN Range acceleration
                    stream_headers = {
                        "Range": "bytes=0-",
                        "Referer": "https://www.tiktok.com/",
                        "Accept-Encoding": "identity"
                    }
                    vid_resp = worker_session.get(video_url, headers=stream_headers, stream=True, timeout=(5, 30))
                    vid_resp.raise_for_status()
                    expected_content_len = int(vid_resp.headers.get("Content-Length", 0))

                    with open(part_filepath, "wb") as f:
                        for chunk in vid_resp.iter_content(chunk_size=1024 * 256):
                            if self.should_stop:
                                break
                            if chunk:
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                                with self.lock:
                                    self.total_bytes_downloaded += len(chunk)

                    if self.should_stop:
                        if os.path.exists(part_filepath):
                            try:
                                os.remove(part_filepath)
                            except Exception:
                                pass
                        break

                    # Automated Video Integrity Verification
                    is_valid, reason = verify_video_file(part_filepath, expected_content_len)
                    if not is_valid:
                        last_err = f"Integrity check failed ({reason})"
                        if os.path.exists(part_filepath):
                            try:
                                os.remove(part_filepath)
                            except Exception:
                                pass
                        continue

                    # Atomic file commit
                    if os.path.exists(final_filepath):
                        try:
                            os.remove(final_filepath)
                        except Exception:
                            pass
                    os.replace(part_filepath, final_filepath)

                    # Update item properties to match file on disk
                    item["filename"] = final_filename
                    item["filepath"] = final_filepath
                    item["cover_path"] = final_coverpath
                    item["title"] = meta_title

                    success = True
                    break
                except Exception as ex:
                    last_err = str(ex)

            fsize_mb = (downloaded_bytes / (1024 * 1024)) if downloaded_bytes > 0 else 0
            size_str = f"{fsize_mb:.1f} MB" if fsize_mb > 0 else "--"

            with self.lock:
                self.processed_count += 1
                if success:
                    self.success_count += 1
                    item["title"] = meta_title or item["title"]
                    item["author"] = meta_author
                    item["status"] = "✅ Done"
                    item["size"] = size_str
                    self.root.after(0, self.update_row_in_tree, idx, meta_title, "✅ Done", size_str)
                    self.root.after(0, self.log, f"✅ [T{worker_id}] Saved Episode {idx}: {final_filename} ({size_str})", "success")
                else:
                    if not self.should_stop:
                        item["status"] = "❌ Failed"
                        self.failed_items.append({"idx": idx, "url": url, "filename": filename, "ep_str": ep_str, "error": last_err})
                        self.root.after(0, self.update_row_in_tree, idx, None, "❌ Failed", "--")
                        self.root.after(0, self.log, f"❌ [T{worker_id}] Failed Episode {idx}: {last_err}", "error")

                self.root.after(0, self.update_batch_progress)

            self.download_queue.task_done()
            if not self.should_stop:
                time.sleep(delay)

    def update_batch_progress(self):
        failed_count = len(self.failed_items)
        elapsed = max(0.1, time.time() - self.start_time)
        mb_downloaded = self.total_bytes_downloaded / (1024 * 1024)
        speed_mb = mb_downloaded / elapsed

        percent = (self.processed_count / self.total_count * 100) if self.total_count else 0
        self.progress_bar.set_progress(self.processed_count, self.total_count)

        self.metrics_label.config(
            text=f"Progress: {self.processed_count}/{self.total_count} ({percent:.1f}%) | Success: {self.success_count} | Failed: {failed_count} | Total: {mb_downloaded:.1f} MB @ {speed_mb:.2f} MB/s"
        )

    def supervisor_loop(self):
        while any(w.is_alive() for w in self.active_workers):
            for w in self.active_workers:
                w.join(timeout=0.2)
            if self.should_stop:
                break

        self.root.after(0, self.on_batch_completed)

    def on_batch_completed(self):
        self.is_downloading = False
        self.toggle_download_btn.config(text="▶ Start Batch Download", style="PrimaryBtn.TButton")

        elapsed = max(1, int(time.time() - self.start_time))
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        total_mb = self.total_bytes_downloaded / (1024 * 1024)

        failed_count = len(self.failed_items)
        if failed_count > 0:
            self.copy_failed_btn.config(state="normal")

        self.send_desktop_notification(f"Download Completed ({self.success_count}/{self.total_count}) in {time_str}")

        if not self.should_stop:
            percent = (self.success_count / self.total_count * 100) if self.total_count else 0
            self.metrics_label.config(
                text=f"🎉 Completed in {time_str}! Success: {self.success_count}/{self.total_count} ({percent:.1f}%) | Total: {total_mb:.1f} MB | Failed: {failed_count}"
            )
            self.log(f"🎉 Batch Finished in {time_str}! Success: {self.success_count}/{self.total_count}, Size: {total_mb:.1f} MB", tag="info")
            
            if failed_count == 0:
                messagebox.showinfo("Download Complete", f"All {self.success_count} episodes downloaded successfully in {time_str}!\nTotal: {total_mb:.1f} MB")
            else:
                messagebox.showwarning(
                    "Download Finished with Errors",
                    f"Successfully downloaded {self.success_count}/{self.total_count} videos ({total_mb:.1f} MB) in {time_str}.\n{failed_count} video(s) failed.\n\nYou can click '🔁 Retry' in the table on any failed episode to re-download."
                )
        else:
            self.metrics_label.config(text="Download stopped by user.")
            self.log("⚠️ Download queue stopped by user.", tag="warn")

    def send_desktop_notification(self, message):
        try:
            if sys.platform == "linux":
                subprocess.Popen(["notify-send", "TikTok Downloader", message])
            elif sys.platform == "darwin":
                subprocess.Popen(["osascript", "-e", f'display notification "{message}" with title "TikTok Downloader"'])
        except Exception:
            pass

    def stop_download(self):
        if self.is_downloading:
            self.should_stop = True
            self.log("Stopping active worker threads, please wait...", tag="warn")
            while not self.download_queue.empty():
                try:
                    self.download_queue.get_nowait()
                    self.download_queue.task_done()
                except Exception:
                    break

    def on_app_close(self):
        if self.is_downloading:
            self.should_stop = True
            while not self.download_queue.empty():
                try:
                    self.download_queue.get_nowait()
                    self.download_queue.task_done()
                except Exception:
                    break

        # Zero Ghost Process: Cleanly shutdown server
        if hasattr(self, 'bridge_server') and self.bridge_server:
            try:
                threading.Thread(target=self.bridge_server.shutdown, daemon=True).start()
            except Exception:
                pass

        try:
            save_dir = self.save_dir_var.get().strip()
            if os.path.exists(save_dir):
                for f in os.listdir(save_dir):
                    fpath = os.path.join(save_dir, f)
                    if os.path.isfile(fpath) and os.path.getsize(fpath) == 0:
                        os.remove(fpath)
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

        os._exit(0)


def main():
    if "--smoke-test" in sys.argv or "--test" in sys.argv:
        print("[CI-SMOKE-TEST] Starting automated binary & GUI smoke test...")
        
        # 1. Verify resource paths in frozen bundle
        for res in ["extractor.js", "bookmarklet.txt"]:
            res_path = get_resource_path(res)
            if not os.path.exists(res_path):
                print(f"[CI-SMOKE-TEST ERROR] Bundled resource missing: {res_path}")
                sys.exit(1)
            print(f"[CI-SMOKE-TEST OK] Bundled resource verified: {res}")

        # 2. Test Tkinter initialization & UI construction
        root = tk.Tk()
        root.withdraw()  # Keep hidden during headless smoke test
        app = TikTokDownloaderApp(root)
        print("[CI-SMOKE-TEST OK] Tkinter UI, ttk styles, and Canvas mounted successfully.")

        # 3. Test Bridge HTTP Server
        time.sleep(0.5)
        try:
            resp = requests.get(f"http://{BRIDGE_HOST}:{BRIDGE_PORT}/api/ping", timeout=3)
            if resp.status_code == 200 and resp.json().get("status") == "ok":
                print("[CI-SMOKE-TEST OK] Bridge server active and successfully answered ping.")
            else:
                print(f"[CI-SMOKE-TEST ERROR] Unexpected bridge ping status: {resp.status_code}")
                sys.exit(1)
        except Exception as e:
            print(f"[CI-SMOKE-TEST ERROR] Failed to connect to bridge server: {e}")
            sys.exit(1)

        print("[CI-SMOKE-TEST OK] All checks passed! Tearing down cleanly...")
        app.on_app_close()
        sys.exit(0)

    lock = SingleInstanceLock()
    if not lock.acquire():
        # Another instance is already running; ping it to bring to front
        try:
            requests.post(f"http://{BRIDGE_HOST}:{BRIDGE_PORT}/api/bring-to-front", timeout=1.0)
        except Exception:
            pass
        print("Another instance of TikTok Downloader is already running. Brought existing window to front.")
        sys.exit(0)

    root = tk.Tk()
    app = TikTokDownloaderApp(root)
    try:
        root.mainloop()
    finally:
        lock.release()

if __name__ == "__main__":
    main()

