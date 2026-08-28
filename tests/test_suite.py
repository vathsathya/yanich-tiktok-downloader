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
         patch("tkinter.messagebox.askyesno", return_value=True), \
         patch("main.messagebox.showinfo"), \
         patch("main.messagebox.showwarning"), \
         patch("main.messagebox.showerror"), \
         patch("main.messagebox.askyesno", return_value=True):
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
    @patch("main.requests.Session.post")
    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_tikwm_primary(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 0,
            "data": {
                "hdplay": "https://tikwm.com/video/media_hd.mp4",
                "play": "https://tikwm.com/video/media.mp4",
                "cover": "https://tikwm.com/cover.jpg",
                "title": "Amazing TikTok Drama Episode 1",
                "author": {"nickname": "Drama Queen"}
            }
        }
        mock_post.return_value = mock_resp
        mock_get.return_value = mock_resp

        result = main.extract_tiktok_metadata("https://www.tiktok.com/@test/video/1234567890123456789")
        assert result["success"] is True
        assert result["video_url"] == "https://tikwm.com/video/media_hd.mp4"
        assert result["cover_url"] == "https://tikwm.com/cover.jpg"
        assert result["title"] == "Amazing TikTok Drama Episode 1"
        assert result["author"] == "Drama Queen"
        assert result["source"].startswith("TikWM")

    @patch("main.requests.Session.post")
    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_fallback_tiklydown(self, mock_get, mock_post):
        mock_post.side_effect = Exception("TikWM post fail")
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

    @patch("main.requests.Session.post")
    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_all_fail(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.side_effect = Exception("API error")
        mock_get.return_value = mock_resp
        mock_post.return_value = mock_resp

        result = main.extract_tiktok_metadata("https://www.tiktok.com/@test/video/1234567890123456789")
        assert result["success"] is False
        assert "Failed to extract" in result["error"] or "Extraction failed" in result["error"]

    @patch("main.requests.Session.post")
    @patch("main.requests.Session.get")
    def test_extract_tiktok_metadata_shortdrama_canonical(self, mock_get, mock_post):
        def post_side_effect(url, **kwargs):
            data_arg = kwargs.get("data", {})
            req_url = data_arg.get("url", "")
            resp = MagicMock()
            if "/shortdrama/episode/" in req_url:
                resp.status_code = 500
                resp.json.return_value = {"code": -1}
            elif "7667927678226043925" in req_url:
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

        mock_post.side_effect = post_side_effect
        mock_get.return_value = MagicMock(status_code=500)
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

    def test_hybrid_nested_treeview_and_cascading_selection(self, app_instance):
        app, root, tmp_path = app_instance
        app.clear_all_items()

        # 1. Add Series items
        series_items = [
            {"episode": 1, "url": "https://www.tiktok.com/@user/video/1111111111111111111"},
            {"episode": 2, "url": "https://www.tiktok.com/@user/video/2222222222222222222"}
        ]
        app.load_urls_into_queue(series_items, series_title="The CEO Secret")

        # 2. Add Standalone item
        single_item = ["https://www.tiktok.com/@user/video/3333333333333333333"]
        app.load_urls_into_queue(single_item)

        # Check tree nodes
        root_children = app.tree.get_children("")
        # Should have 2 root nodes: 1 series parent node and 1 standalone video node
        assert len(root_children) == 2
        series_node = [node for node in root_children if node.startswith("series_")][0]
        standalone_node = [node for node in root_children if not node.startswith("series_")][0]

        # Check series children
        series_children = app.tree.get_children(series_node)
        assert len(series_children) == 2
        assert set(series_children) == {"1", "2"}
        assert standalone_node == "3"

        # Check initial selection
        assert app.tree.set(series_node, "select") == "☑"

        # Toggle series selection via simulated event
        mock_event = MagicMock()
        mock_event.x = 10
        mock_event.y = 10
        with patch.object(app.tree, "identify_region", return_value="cell"), \
             patch.object(app.tree, "identify_column", return_value="#1"), \
             patch.object(app.tree, "identify_row", return_value=series_node):
            app.on_tree_click(mock_event)

        # Series children should now be deselected
        assert not app.queue_items[0]["selected"]
        assert not app.queue_items[1]["selected"]
        assert app.queue_items[2]["selected"] # standalone remains selected
        assert app.tree.set(series_node, "select") == "☐"

        # Test partial selection
        app.queue_items[0]["selected"] = True
        app.update_series_parent_row(series_node)
        assert app.tree.set(series_node, "select") == "◼"

    def test_auto_save_and_restore_session(self, app_instance, tmp_path):
        app, root, _ = app_instance
        app.clear_all_items()
        test_state_file = str(tmp_path / "test_app_state.json")

        with patch("main.get_app_state_path", return_value=test_state_file):
            items = [
                {"episode": 1, "url": "https://www.tiktok.com/@user/video/1111111111111111111"},
                {"episode": 2, "url": "https://www.tiktok.com/@user/video/2222222222222222222"}
            ]
            app.load_urls_into_queue(items, series_title="Persisted Drama")
            app.threads_var.set(4)
            app.save_app_state()

            assert os.path.exists(test_state_file)
            with open(test_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["settings"]["threads"] == 4
            assert len(data["queue"]) == 2

            # Now create a fresh app and test load_app_state
            app.clear_all_items()
            app.threads_var.set(1)
            assert len(app.queue_items) == 0

            app.load_app_state()
            assert len(app.queue_items) == 2
            assert app.threads_var.get() == 4
            assert app.queue_items[0]["series_title"] == "Persisted Drama"

    def test_auto_clipboard_watcher(self, app_instance):
        app, root, _ = app_instance
        app.clear_all_items()
        app.auto_clipboard_var.set(True)

        test_urls = ["https://www.tiktok.com/@user/video/9999999999999999999"]
        app.handle_auto_clipboard_urls(test_urls)

        # Modal should be open with links pre-filled
        assert hasattr(app, "_active_add_modal") and app._active_add_modal.winfo_exists()
        modal = app._active_add_modal
        assert test_urls[0] in modal.url_text.get("1.0", "end")
        
        # Test submitting from the smart modal with series title
        modal.series_title_var.set("Test Drama Series")
        modal.submit_links()

        assert len(app.queue_items) == 1
        assert app.queue_items[0]["url"] == test_urls[0]
        assert app.queue_items[0]["series_title"] == "Test Drama Series"

    def test_toggle_activity_log_view(self, app_instance):
        app, root, _ = app_instance
        assert app.activity_expanded is False
        assert app.log_text.cget("height") == 2

        app.toggle_activity_log_view()
        assert app.activity_expanded is True
        assert app.log_text.cget("height") == 9

        app.toggle_activity_log_view()
        assert app.activity_expanded is False
        assert app.log_text.cget("height") == 2

    def test_settings_modal(self, app_instance):
        app, root, _ = app_instance
        modal = main.SettingsModal(root, app)
        assert modal.winfo_exists()
        
        # Test modifying settings from modal
        app.threads_var.set(4)
        app.skip_existing_var.set(False)
        modal.save_and_close()
        assert not modal.winfo_exists()
        assert app.threads_var.get() == 4
        assert app.skip_existing_var.get() is False

    def test_embed_mp4_metadata_mocked(self, tmp_path):
        dummy_mp4 = tmp_path / "test.mp4"
        dummy_mp4.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 2000)

        with patch("subprocess.run") as mock_subp:
            mock_subp.return_value = MagicMock(returncode=0)
            with patch("os.replace") as mock_replace:
                with patch("os.path.exists", return_value=True), patch("os.path.getsize", return_value=5000):
                    res = main.embed_mp4_metadata(
                        str(dummy_mp4),
                        title="Test Title",
                        series_title="Test Drama",
                        author="Test Creator",
                        ep_num=1,
                        total_eps=10
                    )
                    assert res is True
                    assert mock_subp.called


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
        # Ensure series poster cover.jpg is downloaded
        assert os.path.exists(os.path.join(save_dir, "cover.jpg"))

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


class TestAutoUpdater:
    def test_parse_version_tuple(self):
        assert main.parse_version_tuple("v1.2.3") == (1, 2, 3, 0)
        assert main.parse_version_tuple("1.0.0") == (1, 0, 0, 0)
        assert main.parse_version_tuple("v2.1.0-beta") == (2, 1, 0, 0)
        assert main.parse_version_tuple("v1.2.0") > main.parse_version_tuple("1.0.0")
        assert main.parse_version_tuple("v1.0.1") > main.parse_version_tuple("v1.0.0")
        assert main.parse_version_tuple("v1.0.0") == main.parse_version_tuple("1.0.0")
        assert main.parse_version_tuple("") == (0, 0, 0, 0)

    @patch("main.requests.get")
    def test_updater_up_to_date(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v1.0.0",
            "body": "No changes",
            "assets": []
        }
        mock_get.return_value = mock_resp

        updater = main.SilentAutoUpdater(app_version="1.0.0", repo="test/repo")
        updater.staging_dir = str(tmp_path / "updates")

        callback_called = []
        updater._worker_routine(callback_on_ready=lambda info: callback_called.append(info))
        assert len(callback_called) == 0

    @patch("main.requests.get")
    def test_updater_download_new_version(self, mock_get, tmp_path):
        import zipfile
        staging = str(tmp_path / "updates")
        dummy_zip_content = b"PK\x05\x06" + b"\x00" * 18 # Minimal empty zip

        def mock_get_side_effect(url, **kwargs):
            resp = MagicMock()
            if "releases/latest" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "tag_name": "v1.5.0",
                    "body": "Awesome new features!",
                    "assets": [
                        {
                            "name": "TikTokDownloader-Windows-x64.zip",
                            "browser_download_url": "https://example.com/TikTokDownloader-Windows-x64.zip"
                        },
                        {
                            "name": "TikTokDownloader-Linux-x64.tar.gz",
                            "browser_download_url": "https://example.com/TikTokDownloader-Linux-x64.tar.gz"
                        }
                    ]
                }
            else:
                resp.status_code = 200
                resp.iter_content.return_value = [dummy_zip_content]
                resp.__enter__.return_value = resp
            return resp

        mock_get.side_effect = mock_get_side_effect

        updater = main.SilentAutoUpdater(app_version="1.0.0", repo="test/repo")
        updater.staging_dir = staging

        callback_info = []
        with patch("sys.platform", "win32"):
            updater._worker_routine(callback_on_ready=lambda info: callback_info.append(info))

        assert len(callback_info) == 1
        info = callback_info[0]
        assert info["version"] == "v1.5.0"
        assert info["current_version"] == "1.0.0"
        assert "Awesome new features" in info["release_notes"]
        assert os.path.exists(info["archive_path"])

    def test_update_ready_modal_lifecycle(self, tk_root):
        confirm_called = []
        info = {
            "version": "v1.2.0",
            "current_version": "1.0.0",
            "release_notes": "- Faster downloads\n- Silent auto-updater",
            "archive_path": "dummy.zip",
            "asset_name": "TikTokDownloader.zip"
        }

        modal = main.UpdateReadyModal(tk_root, info, on_update_confirm=lambda: confirm_called.append(True))
        tk_root.update()

        assert modal.winfo_exists()
        assert modal.apply_btn is not None
        assert modal.later_btn is not None
        assert modal.apply_btn.cget("text") == "⚡ Update & Restart Now"
        assert modal.later_btn.cget("text") == "Remind Me Later"
        modal.confirm_update()
        assert len(confirm_called) == 1

    @patch("main.requests.get")
    def test_manual_check_update_up_to_date(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v1.0.0",
            "body": "No updates",
            "assets": []
        }
        mock_get.return_value = mock_resp

        updater = main.SilentAutoUpdater(app_version="1.0.0", repo="test/repo")
        no_update_called = []
        updater._worker_routine(callback_on_ready=None, on_no_update=lambda reason: no_update_called.append(reason))
        assert len(no_update_called) == 1
        assert no_update_called[0] == "up_to_date"

    @patch("main.requests.get")
    def test_end_to_end_update_detection_and_apply(self, mock_get, tmp_path, tk_root):
        staging = str(tmp_path / "updates")
        dummy_zip_content = b"PK\x05\x06" + b"\x00" * 18

        def mock_get_side_effect(url, **kwargs):
            resp = MagicMock()
            if "releases/latest" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "tag_name": "v1.2.6",
                    "body": "Version 1.2.6 update notes",
                    "assets": [
                        {
                            "name": "TikTokDownloader-Windows-AMD64.zip",
                            "browser_download_url": "https://example.com/TikTokDownloader-Windows-AMD64.zip"
                        }
                    ]
                }
            else:
                resp.status_code = 200
                resp.iter_content.return_value = [dummy_zip_content]
                resp.__enter__.return_value = resp
            return resp

        mock_get.side_effect = mock_get_side_effect

        app = main.TikTokDownloaderApp(tk_root)
        app.updater.staging_dir = staging

        callback_data = []
        with patch("sys.platform", "win32"):
            app.updater._worker_routine(callback_on_ready=lambda info: callback_data.append(info))

        assert len(callback_data) == 1
        update_info = callback_data[0]
        assert update_info["version"] == "v1.2.6"
        assert update_info["current_version"] == "1.2.5"

        # Test apply in dev mode safely
        with patch("main.messagebox.showinfo") as mock_box:
            res = main.apply_update_and_restart(update_info, app_instance=app)
            assert res is True
