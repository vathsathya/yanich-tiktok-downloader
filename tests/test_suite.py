import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import socket
import pytest
import threading
import requests
import tkinter as tk
from unittest.mock import patch, MagicMock

import main

# Autouse fixture to prevent blocking Tkinter dialogs in tests
@pytest.fixture(autouse=True)
def mock_messageboxes():
    with patch("tkinter.messagebox.showinfo"), \
         patch("tkinter.messagebox.showwarning"), \
         patch("tkinter.messagebox.showerror"), \
         patch("tkinter.messagebox.askyesno", return_value=True):
        yield


class TestRegexAndNormalization:
    def test_tiktok_url_regex(self):
        valid_urls = [
            "https://www.tiktok.com/@user/video/7123456789012345678",
            "https://vt.tiktok.com/ZS1234567/",
            "https://vm.tiktok.com/ZM1234567/",
            "http://m.tiktok.com/v/7123456789012345678.html",
            "https://www.tiktok.com/@creator/video/7483920182736451928?is_from_webapp=1&sender_device=pc"
        ]
        for url in valid_urls:
            match = main.TIKTOK_URL_RE.search(url)
            assert match is not None, f"Should match valid URL: {url}"

        invalid_text = "Not a tiktok url http://google.com or plain text"
        assert main.TIKTOK_URL_RE.search(invalid_text) is None

    def test_normalize_tiktok_url(self):
        url1 = "https://www.tiktok.com/@user/video/7123456789012345678?param=1&share=true"
        url2 = "https://www.tiktok.com/@other/video/7123456789012345678"
        assert main.normalize_tiktok_url(url1) == "tt_video_7123456789012345678"
        assert main.normalize_tiktok_url(url1) == main.normalize_tiktok_url(url2)

        drama_ep1 = "https://www.tiktok.com/shortdrama/episode/7667927678226043925/1"
        drama_ep2 = "https://www.tiktok.com/shortdrama/episode/7667927678226043925/2"
        assert main.normalize_tiktok_url(drama_ep1) == "tt_shortdrama_7667927678226043925_ep_1"
        assert main.normalize_tiktok_url(drama_ep2) == "tt_shortdrama_7667927678226043925_ep_2"
        assert main.normalize_tiktok_url(drama_ep1) != main.normalize_tiktok_url(drama_ep2)

        short_url = "https://vt.tiktok.com/ZS1234567/"
        assert main.normalize_tiktok_url(short_url) == "https://vt.tiktok.com/zs1234567"
        assert main.normalize_tiktok_url("") == ""
        assert main.normalize_tiktok_url(None) == ""

    def test_filename_clean_regex(self):
        dirty = 'My:Video/Title\\with*Bad?"Chars<>|and\nNewlines'
        clean = main.FILENAME_CLEAN_RE.sub('_', dirty)
        assert ":" not in clean and "/" not in clean and "\\" not in clean
        assert "*" not in clean and "?" not in clean and "<" not in clean


class TestSingleInstanceLock:
    def test_lock_acquire_and_release(self):
        test_port = 54329
        lock1 = main.SingleInstanceLock(port=test_port)
        assert lock1.acquire() is True
        assert lock1.is_locked is True

        # Second lock attempt on same port should fail
        lock2 = main.SingleInstanceLock(port=test_port)
        assert lock2.acquire() is False
        assert lock2.is_locked is False

        # Release first lock
        lock1.release()
        assert lock1.is_locked is False

        # Now second lock should succeed
        assert lock2.acquire() is True
        lock2.release()


class TestVideoVerification:
    def test_verify_nonexistent_file(self, tmp_path):
        fpath = str(tmp_path / "nonexistent.mp4")
        valid, reason = main.verify_video_file(fpath)
        assert valid is False
        assert "File not found" in reason

    def test_verify_too_small_file(self, tmp_path):
        fpath = str(tmp_path / "small.mp4")
        with open(fpath, "wb") as f:
            f.write(b"tiny data" * 10)
        valid, reason = main.verify_video_file(fpath)
        assert valid is False
        assert "File too small" in reason

    def test_verify_invalid_header_file(self, tmp_path):
        fpath = str(tmp_path / "corrupt.mp4")
        with open(fpath, "wb") as f:
            f.write(b"\x00" * (40 * 1024))
        valid, reason = main.verify_video_file(fpath)
        assert valid is False
        assert "Missing valid MP4 container header" in reason

    @patch("subprocess.run")
    def test_verify_valid_header_file(self, mock_subp, tmp_path):
        mock_subp.return_value = MagicMock(returncode=0, stdout=b'{"streams": [{"codec_name": "h264"}]}')
        fpath = str(tmp_path / "valid_dummy.mp4")
        with open(fpath, "wb") as f:
            f.write(b"\x00\x00\x00\x20ftypisom" + b"\x00" * (50 * 1024))
        valid, reason = main.verify_video_file(fpath)
        assert valid is True
        assert reason == "Valid"


class TestHttpBridgeServer:
    @pytest.fixture(scope="class")
    def bridge_server(self):
        test_port = 54328
        server = main.ReusableHTTPServer(("127.0.0.1", test_port), main.BridgeRequestHandler)
        mock_app = MagicMock()
        mock_app.root = MagicMock()
        server.app = mock_app

        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)
        yield server, test_port, mock_app
        server.shutdown()
        server.server_close()

    def test_ping_endpoint(self, bridge_server):
        server, port, _ = bridge_server
        res = requests.get(f"http://127.0.0.1:{port}/api/ping")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert data.get("app") == "TikTokDownloader"
        assert "Access-Control-Allow-Origin" in res.headers

    def test_setup_endpoint(self, bridge_server):
        server, port, _ = bridge_server
        res = requests.get(f"http://127.0.0.1:{port}/setup")
        assert res.status_code == 200
        assert "1-Click Browser Setup" in res.text
        assert "text/html" in res.headers.get("Content-Type", "")

    def test_extractor_endpoint(self, bridge_server):
        server, port, _ = bridge_server
        res = requests.get(f"http://127.0.0.1:{port}/extractor.js")
        assert res.status_code == 200
        assert len(res.content) > 0

    def test_options_cors(self, bridge_server):
        server, port, _ = bridge_server
        res = requests.options(f"http://127.0.0.1:{port}/api/receive-links")
        assert res.status_code == 200
        assert res.headers.get("Access-Control-Allow-Origin") == "*"

    def test_receive_links_json_list(self, bridge_server):
        server, port, mock_app = bridge_server
        payload = [
            {"episode": 1, "url": "https://www.tiktok.com/@user/video/1111111111111111111"},
            {"episode": 2, "url": "https://www.tiktok.com/@user/video/2222222222222222222"}
        ]
        res = requests.post(f"http://127.0.0.1:{port}/api/receive-links", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "success"
        assert data.get("count") == 2

    def test_receive_links_json_dict_with_title(self, bridge_server):
        server, port, mock_app = bridge_server
        payload = {
            "title": "My Drama Series",
            "episodes": [
                {"episode": 1, "url": "https://www.tiktok.com/@user/video/3333333333333333333"}
            ]
        }
        res = requests.post(f"http://127.0.0.1:{port}/api/receive-links", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "success"
        assert data.get("count") == 1

    def test_receive_links_plain_text(self, bridge_server):
        server, port, mock_app = bridge_server
        payload = "https://www.tiktok.com/@user/video/4444444444444444444\nhttps://www.tiktok.com/@user/video/5555555555555555555"
        res = requests.post(f"http://127.0.0.1:{port}/api/receive-links", data=payload, headers={"Content-Type": "text/plain"})
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "success"
        assert data.get("count") == 2

    def test_bring_to_front(self, bridge_server):
        server, port, mock_app = bridge_server
        res = requests.post(f"http://127.0.0.1:{port}/api/bring-to-front")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"


class TestMetadataExtraction:
    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_tikwm_primary(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 0,
            "data": {
                "play": "https://tikwm.com/video/media.mp4",
                "cover": "https://tikwm.com/cover.jpg",
                "title": "Amazing TikTok Drama Episode 1",
                "author": {"nickname": "Drama Queen"}
            }
        }
        mock_get.return_value = mock_resp

        result = main.extract_tiktok_metadata("https://www.tiktok.com/@test/video/1234567890123456789")
        assert result["success"] is True
        assert result["video_url"] == "https://tikwm.com/video/media.mp4"
        assert result["cover_url"] == "https://tikwm.com/cover.jpg"
        assert result["title"] == "Amazing TikTok Drama Episode 1"
        assert result["author"] == "Drama Queen"
        assert result["source"] == "TikWM"

    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_fallback_tiklydown(self, mock_get):
        def side_effect(url, **kwargs):
            resp = MagicMock()
            if "tikwm" in url:
                resp.status_code = 500
                resp.json.return_value = {"code": -1}
            elif "tiklydown" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "video": {"noWatermark": "https://tiklydown.com/stream.mp4", "cover": "https://tiklydown.com/c.jpg"},
                    "title": "Fallback Video Title",
                    "author": {"name": "Fallback Creator"}
                }
            return resp

        mock_get.side_effect = side_effect
        result = main.extract_tiktok_metadata("https://www.tiktok.com/@test/video/1234567890123456789")
        assert result["success"] is True
        assert result["video_url"] == "https://tiklydown.com/stream.mp4"
        assert result["title"] == "Fallback Video Title"
        assert result["source"] == "Tiklydown"

    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_all_fail(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.side_effect = Exception("API error")
        mock_get.return_value = mock_resp

        result = main.extract_tiktok_metadata("https://www.tiktok.com/@test/video/1234567890123456789")
        assert result["success"] is False
        assert "Extraction failed" in result["error"]

    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_shortdrama_canonical(self, mock_get):
        def side_effect(url, **kwargs):
            resp = MagicMock()
            if "/shortdrama/episode/" in url:
                resp.status_code = 500
                resp.json.return_value = {"code": -1}
            elif "7667927678226043925" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "code": 0,
                    "data": {
                        "play": "https://tikwm.com/video/drama_ep1.mp4",
                        "cover": "https://tikwm.com/cover1.jpg",
                        "title": "Drama Episode 1",
                        "author": {"nickname": "Drama Series"}
                    }
                }
            else:
                resp.status_code = 500
            return resp

        mock_get.side_effect = side_effect
        result = main.extract_tiktok_metadata("https://www.tiktok.com/shortdrama/episode/7667927678226043925/1")
        assert result["success"] is True
        assert result["video_url"] == "https://tikwm.com/video/drama_ep1.mp4"
        assert result["source"] == "TikWM-Canonical"


# Session-scoped Tkinter root to avoid Tcl interpreter re-init issues
@pytest.fixture(scope="session")
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        try:
            root.destroy()
        except Exception:
            pass
    except tk.TclError:
        pytest.skip("Tkinter display ($DISPLAY) not available in this environment")


class TestTkinterAppLifecycle:
    @pytest.fixture
    def app_instance(self, tk_root, tmp_path):
        app = main.TikTokDownloaderApp(tk_root)
        app.clear_all_items()
        app.clear_logs()
        app.base_save_dir = str(tmp_path / "downloads")
        app.save_dir_var.set(app.base_save_dir)
        yield app, tk_root, tmp_path
        app.clear_all_items()
        app.clear_logs()

    def test_app_initial_state(self, app_instance):
        app, root, tmp_path = app_instance
        assert app.is_downloading is False
        assert len(app.queue_items) == 0
        assert app.count_badge.cget("text") == "0 / 0 Selected"

    def test_load_urls_and_deduplication(self, app_instance):
        app, root, tmp_path = app_instance
        items = [
            {"episode": 1, "url": "https://www.tiktok.com/@user/video/1111111111111111111"},
            {"episode": 2, "url": "https://www.tiktok.com/@user/video/2222222222222222222"},
            {"episode": 2, "url": "https://www.tiktok.com/@user/video/2222222222222222222?track=1"} # duplicate
        ]
        app.load_urls_into_queue(items, series_title="Romance In Seoul")
        
        assert len(app.queue_items) == 2
        assert app.queue_items[0]["ep_str"] == "01"
        assert app.queue_items[1]["ep_str"] == "02"
        assert "Romance In Seoul" in app.prefix_var.get()
        assert app.count_badge.cget("text") == "2 / 2 Selected"

    def test_load_shortdrama_urls_into_queue(self, app_instance):
        app, root, tmp_path = app_instance
        drama_episodes = [
            "https://www.tiktok.com/shortdrama/episode/7667927678226043925/1",
            "https://www.tiktok.com/shortdrama/episode/7667927678226043925/2",
            "https://www.tiktok.com/shortdrama/episode/7667927678226043925/3",
            "https://www.tiktok.com/shortdrama/episode/7667927678226043925/1?is_copy_url=1" # duplicate of ep 1
        ]
        app.load_urls_into_queue(drama_episodes, series_title="CEO Secret Love")
        assert len(app.queue_items) == 3
        assert app.queue_items[0]["ep_str"] == "01"
        assert app.queue_items[1]["ep_str"] == "02"
        assert app.queue_items[2]["ep_str"] == "03"
        assert "CEO Secret Love" in app.prefix_var.get()

    def test_load_urls_with_blob_url_sanitization(self, app_instance):
        app, root, tmp_path = app_instance
        items = [
            {"episode": 1, "url": "https://www.tiktok.com/@user/video/1111111111111111111", "video_url": "blob:https://www.tiktok.com/123-abc", "cover_url": "blob:https://www.tiktok.com/cov-123"},
            {"episode": 2, "url": "https://www.tiktok.com/@user/video/2222222222222222222", "video_url": "https://v16.tiktokcdn.com/valid.mp4", "cover_url": "https://p16.tiktokcdn.com/cover.jpg"}
        ]
        app.load_urls_into_queue(items)
        assert len(app.queue_items) == 2
        assert app.queue_items[0]["video_url"] == ""
        assert app.queue_items[0]["cover_url"] == ""
        assert app.queue_items[1]["video_url"] == "https://v16.tiktokcdn.com/valid.mp4"
        assert app.queue_items[1]["cover_url"] == "https://p16.tiktokcdn.com/cover.jpg"

    def test_toggle_selection(self, app_instance):
        app, root, tmp_path = app_instance
        items = [
            "https://www.tiktok.com/@user/video/1111111111111111111",
            "https://www.tiktok.com/@user/video/2222222222222222222"
        ]
        app.load_urls_into_queue(items)
        assert all(it["selected"] for it in app.queue_items)

        # Deselect all
        app.toggle_select_all_items()
        assert not any(it["selected"] for it in app.queue_items)
        assert app.count_badge.cget("text") == "0 / 2 Selected"

        # Select all again
        app.toggle_select_all_items()
        assert all(it["selected"] for it in app.queue_items)
        assert app.count_badge.cget("text") == "2 / 2 Selected"

    def test_remove_and_clear_items(self, app_instance):
        app, root, tmp_path = app_instance
        items = [
            "https://www.tiktok.com/@user/video/1111111111111111111",
            "https://www.tiktok.com/@user/video/2222222222222222222"
        ]
        app.load_urls_into_queue(items)
        
        # Deselect item 1, keep item 2 selected
        app.queue_items[0]["selected"] = False
        app.remove_selected_items() # removes selected item 2
        assert len(app.queue_items) == 1
        assert app.queue_items[0]["url"] == items[0]

        app.clear_all_items()
        assert len(app.queue_items) == 0

    def test_logging(self, app_instance):
        app, root, tmp_path = app_instance
        app.log("Test info message", tag="info")
        app.log("✅ Download success", tag="success")
        app.log("❌ Download failed", tag="error")
        content = app.log_text.get("1.0", "end-1c")
        assert "Test info message" in content
        assert "Download success" in content
        assert "Download failed" in content

        app.clear_logs()
        assert app.log_text.get("1.0", "end-1c").strip() == ""

    def test_export_and_import_queue(self, app_instance):
        app, root, tmp_path = app_instance
        items = [
            {"episode": 1, "url": "https://www.tiktok.com/@user/video/1111111111111111111"},
            {"episode": 2, "url": "https://www.tiktok.com/@user/video/2222222222222222222"}
        ]
        app.load_urls_into_queue(items, series_title="Test Drama")
        export_file = str(tmp_path / "exported_queue.json")

        with patch("main.filedialog.asksaveasfilename", return_value=export_file):
            app.export_queue()

        assert os.path.exists(export_file)
        with open(export_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["episodes"]) == 2

        # Clear and re-import
        app.clear_all_items()
        assert len(app.queue_items) == 0

        with patch("main.filedialog.askopenfilename", return_value=export_file):
            app.import_queue()

        assert len(app.queue_items) == 2
        assert app.queue_items[0]["url"] == "https://www.tiktok.com/@user/video/1111111111111111111"


class TestDownloadWorkerExecution:
    @patch("subprocess.run")
    @patch("main.extract_tiktok_metadata")
    @patch("main.requests.Session.get")
    def test_simulated_download_success(self, mock_get, mock_extract, mock_subp, tk_root, tmp_path):
        mock_subp.return_value = MagicMock(returncode=0, stdout=b'{"streams": [{"codec_name": "h264"}]}')
        save_dir = str(tmp_path / "downloads")
        os.makedirs(save_dir, exist_ok=True)

        mock_extract.return_value = {
            "success": True,
            "video_url": "https://example.com/video.mp4",
            "cover_url": "https://example.com/cover.jpg",
            "title": "Drama Ep 01",
            "author": "Creator"
        }

        # Mock video streaming content with valid MP4 header
        valid_mp4_content = b"\x00\x00\x00\x20ftypisom" + b"\x00" * (40 * 1024)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": str(len(valid_mp4_content))}
        mock_resp.iter_content.return_value = [valid_mp4_content]
        mock_resp.content = valid_mp4_content
        mock_get.return_value = mock_resp

        app = main.TikTokDownloaderApp(tk_root)
        app.clear_all_items()
        app.base_save_dir = save_dir
        app.save_dir_var.set(save_dir)

        item = {
            "idx": 1,
            "selected": True,
            "ep_str": "01",
            "title": "Drama_Ep_01.mp4",
            "status": "Pending",
            "size": "--",
            "url": "https://www.tiktok.com/@user/video/1111111111111111111",
            "filename": "Drama_Ep_01.mp4",
            "filepath": os.path.join(save_dir, "Drama_Ep_01.mp4"),
            "cover_path": os.path.join(save_dir, "Drama_Ep_01.jpg")
        }
        app.queue_items = [item]
        app.refresh_tree()

        # Run batch download synchronously
        app.download_queue.put(item)
        app.is_downloading = True
        app.should_stop = False
        app.total_count = 1
        app.processed_count = 0
        app.success_count = 0

        app.worker_thread_loop(worker_id=1, save_dir=save_dir)
        tk_root.update()

        assert item["status"] == "✅ Done"
        assert app.success_count == 1
        assert os.path.exists(item["filepath"])
        assert os.path.getsize(item["filepath"]) == len(valid_mp4_content)

    @patch("main.extract_tiktok_metadata")
    def test_simulated_download_stop(self, mock_extract, tk_root, tmp_path):
        save_dir = str(tmp_path / "downloads")
        os.makedirs(save_dir, exist_ok=True)

        app = main.TikTokDownloaderApp(tk_root)
        app.clear_all_items()
        app.base_save_dir = save_dir
        app.save_dir_var.set(save_dir)

        app.is_downloading = True
        app.should_stop = True # stopped immediately

        item = {
            "idx": 1,
            "selected": True,
            "ep_str": "01",
            "title": "Drama_Ep_01.mp4",
            "status": "Pending",
            "size": "--",
            "url": "https://www.tiktok.com/@user/video/1111111111111111111",
            "filename": "Drama_Ep_01.mp4",
            "filepath": os.path.join(save_dir, "Drama_Ep_01.mp4"),
            "cover_path": os.path.join(save_dir, "Drama_Ep_01.jpg")
        }
        app.download_queue.put(item)
        app.worker_thread_loop(worker_id=1, save_dir=save_dir)
        tk_root.update()

        # Should exit loop cleanly without downloading
        assert not os.path.exists(item["filepath"])
