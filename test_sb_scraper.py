"""Offline regression tests: python -m unittest test_sb_scraper -v."""
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import requests

import sb_scraper as app


VIDEO = "https://spankbang.com/8fffb/video/example"


def html(url="https://cdn.example.com/video.mp4"):
    return ("<h1 data-testid='video-title'>A title with - hyphens</h1>"
            "<div id='video'><a href='/profile/test-user'>Test User</a></div>"
            "<script>var stream_data = {'1080p': ['" + url + "'], '720p': [], '4k': []};</script>")


class ScraperTests(unittest.TestCase):
    def test_bundled_enhanced_version_and_refresh_configuration(self):
        self.assertEqual(app.cloudscraper.__version__, "3.0.0")
        self.assertEqual(Path(app.cloudscraper.__file__).resolve().parent,
                         Path(app.__file__).resolve().parent / "cloudscraper")
        with patch.object(app.cloudscraper, "create_scraper", wraps=app.cloudscraper.create_scraper) as factory:
            client = app.PageClient()
            try:
                self.assertIsInstance(client.session, app.cloudscraper.CloudScraper)
                self.assertFalse(client.session.auto_refresh_on_403)
                self.assertEqual(client.session.session_refresh_interval, float("inf"))
                self.assertEqual(factory.call_args.kwargs["max_concurrent_requests"], float("inf"))
                self.assertNotEqual(client.session.headers["User-Agent"], "Mozilla/5.0")
            finally:
                client.close()

    def test_http_challenge_falls_back_without_stopping_later_http_requests(self):
        client = app.PageClient()
        response = requests.Response()
        response.status_code = 403
        response._content = b"<title>Just a moment...</title>"
        page = Mock()
        page.goto.return_value.status = 200
        page.title.return_value = "Example"
        page.locator.return_value.is_visible.return_value = False
        page.content.return_value = html()
        context = Mock()
        context.cookies.return_value = []
        def start():
            client.page, client.context = page, context
        try:
            with patch.object(client.session, "get", return_value=response), patch.object(client, "start_browser", side_effect=start) as browser:
                self.assertIn("stream_data", client.get(VIDEO))
                browser.assert_called_once()
            good = requests.Response()
            good.status_code = 200
            good._content = html().encode()
            with patch.object(client.session, "get", return_value=good) as get:
                client.get(VIDEO)
                get.assert_called_once()
        finally:
            client.close()

    def test_request_exception_does_not_leave_throttle_counter_stuck(self):
        client = app.PageClient(browser=False)
        def timeout(*args, **kwargs):
            client.session.current_concurrent_requests = 1
            raise requests.Timeout("temporary timeout")
        try:
            with patch.object(client.session, "get", side_effect=timeout):
                with self.assertRaises(requests.Timeout):
                    client.get(VIDEO)
            self.assertEqual(client.session.current_concurrent_requests, 0)
        finally:
            client.close()

    def test_exact_history_id_instead_of_url_prefix(self):
        self.assertEqual(app.url_key(VIDEO), app.url_key("https://uk.spankbang.com/8fffb/play/other/720p"))
        self.assertNotEqual(app.url_key(VIDEO), app.url_key("https://spankbang.com/8fffc/video/other"))
        self.assertEqual(app.video_id("https://spankbang.com/abc-8fffb/playlist/title"), "8fffb")
        self.assertEqual(app.normalize_url("http://www.spankbang.com/8fffb/video/example#fragment"), VIDEO)
        for url in ["https://spankbang.com.evil.example/8fffb/video/", "https://example.com", "file:///a"]:
            with self.assertRaises(ValueError):
                app.normalize_url(url)

    def test_streams_do_not_require_old_source_tag_or_uploader_markup(self):
        info = app.extract_video(html(), VIDEO)
        self.assertEqual(info["title"], "A title with - hyphens")
        self.assertEqual(info["uploader"], "Test User")
        self.assertEqual(len(info["formats"]), 1)
        self.assertEqual(info["formats"][0]["height"], 1080)
        fallback = app.extract_video('<h1>Only a player</h1><video id="main_video_player"><source src="/v.mp4"></video>', VIDEO)
        self.assertEqual(fallback["uploader"], "Unknown")
        with self.assertRaises(ValueError):
            app.extract_video('<video id="ad-player"><source src="https://ads.example.com/ad.mp4"></video>', VIDEO)

    def test_collection_follows_real_next_and_deduplicates(self):
        pages = ["<h1>Collection</h1><main><a href='/abc-one/playlist/test'>one</a>"
                 "<a href='/one/video/duplicate'>duplicate</a></main><a rel='next' href='?page=2'>Next</a>",
                 "<main><a href='/two/video/title'>two</a></main><a rel='next' href='?page=2'>Next</a>"]
        class Client:
            def __init__(self): self.calls = []
            def get(self, url):
                self.calls.append(url)
                return pages[len(self.calls) - 1]
        client = Client()
        title, urls = app.collect_collection(client, "https://spankbang.com/abc/playlist/test")
        self.assertEqual(title, "Collection")
        self.assertEqual(urls, ["https://spankbang.com/one/video/", "https://spankbang.com/two/video/"])
        self.assertEqual(len(client.calls), 2)

    def test_existing_config_is_read_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.txt"
            value = "ALREADY_DL_TXT: custom-history.txt\n# custom setting\n"
            config.write_text(value)
            with patch.object(app.Path, "cwd", return_value=root):
                self.assertEqual(app.history_path(), root / "custom-history.txt")
            self.assertEqual(config.read_text(), value)

    def test_check_and_failures_never_mark_complete(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(temporary)
            source, history = root / "source.txt", root / "history.txt"
            source.write_text(VIDEO + "\n")
            args = [str(source), "--history", str(history), "-o", str(root / "output")]
            with patch.object(app.PageClient, "get", return_value=html()):
                self.assertEqual(app.main([*args, "--check"]), 0)
            self.assertFalse(history.exists())
            with patch.object(app.PageClient, "get", side_effect=requests.HTTPError("403 blocked")):
                self.assertEqual(app.main(args), 1)
            self.assertFalse(history.exists())
            self.assertIn(VIDEO, (root / "output/failed_dl.txt").read_text())

    def test_real_download_missing_length_fallback_and_history(self):
        payload = b"test-media-bytes" * 1024
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(self.path)
                if self.path == "/high.mp4":
                    self.send_error(403)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                # No Content-Length: the legacy scraper incorrectly failed this.
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                root = Path(temporary)
                source, history = root / "source.txt", root / "history.txt"
                source.write_text(VIDEO + "\nhttps://spankbang.com/other/video/test\n")
                base = f"http://127.0.0.1:{server.server_port}"
                page = html(base + "/high.mp4").replace("'720p': []", "'720p': ['" + base + "/low.mp4']")
                args = [str(source), "--history", str(history), "-o", str(root / "output"), "--no-browser"]
                with patch.object(app.PageClient, "get", side_effect=[page, requests.HTTPError("removed")]):
                    self.assertEqual(app.main(args), 1)
                saved = list((root / "output").glob("*.mp4"))
                self.assertEqual(len(saved), 1)
                self.assertIn("720p", saved[0].name)
                self.assertEqual(saved[0].read_bytes(), payload)
                self.assertEqual(app.read_urls(history), [VIDEO])
                self.assertEqual(calls, ["/high.mp4", "/low.mp4"])
                source.write_text("https://www.spankbang.com/8fffb/video/a-new-slug\n")
                with patch.object(app.PageClient, "get", side_effect=AssertionError("Should skip history")):
                    self.assertEqual(app.main(args), 0)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == "__main__":
    unittest.main()
