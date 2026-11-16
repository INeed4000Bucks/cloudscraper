"""Download SpankBang URLs: python sb_scraper.py source.txt.

Blocked requests use an ordinary, separate Chrome profile. Complete any
verification or terms prompts yourself in that browser window.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
import cloudscraper
from bs4 import BeautifulSoup
from playwright.sync_api import Error as BrowserError, sync_playwright
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def normalize_url(url):
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not (host == "spankbang.com" or host.endswith(".spankbang.com")):
        raise ValueError(f"Not a SpankBang URL: {url.strip()}")
    if parts.username or parts.password or parts.port:
        raise ValueError("URLs must not include credentials or custom ports")
    return urlunsplit(("https", "spankbang.com", parts.path or "/", parts.query, ""))


def video_id(url):
    path = urlsplit(url).path
    match = re.match(r"/([a-z0-9]+)/(?:video|play|embed)(?:/|$)", path)
    if not match:
        match = re.match(r"/[a-z0-9]+-([a-z0-9]+)/playlist/", path)
    return match.group(1) if match else None


def url_key(url):
    return video_id(url) or normalize_url(url).rstrip("/")


def read_urls(path):
    return list(dict.fromkeys(line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()
                             if line.strip() and not line.lstrip().startswith("#")))


def state_directory():
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "CB_DL"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/CB_DL"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "CB_DL"


def history_path():
    candidates = [Path.cwd() / "config.txt", Path(__file__).resolve().parent / "config.txt", state_directory() / "config.txt"]
    config = next((path for path in candidates if path.is_file()), None)
    if config:
        for line in config.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("ALREADY_DL_TXT:"):
                value = line.split(":", 1)[1].strip()
                if not value:
                    break
                path = Path(os.path.expandvars(os.path.expanduser(value)))
                return path if path.is_absolute() else config.parent / path
        raise ValueError(f"Missing ALREADY_DL_TXT in {config}")
    return state_directory() / "already_dl.txt"


def safe_name(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", text).strip(" .")[:120]
    if not text or re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", text, re.I):
        text = "_" + text
    return text


class PageClient:
    """Reuse one HTTP session and, when needed, one normal Chrome window."""

    def __init__(self, *, timeout=30, browser=True, browser_wait=180, profile=None):
        if cloudscraper.__version__ != "3.0.0":
            raise RuntimeError("This downloader requires the bundled cloudscraper 3.0.0; update the complete checkout.")
        # 3.0.0's automatic refresh can recursively re-enter request(). Keep its
        # normal challenge handling, with explicit Chrome fallback for failures.
        self.session = cloudscraper.create_scraper(
            auto_refresh_on_403=False,
            session_refresh_interval=float("inf"),
            # Challenge handlers issue nested requests on this same session.
            # The app is sequential, so a concurrency gate would only deadlock them.
            max_concurrent_requests=float("inf"),
        )
        self.timeout, self.allow_browser, self.browser_wait = timeout, browser, browser_wait
        self.profile = profile or state_directory() / "chrome-profile"
        self.browser = self.context = self.page = self.playwright = self.process = None

    def start_browser(self):
        candidates = [shutil.which("google-chrome"), shutil.which("chrome"), shutil.which("chromium"),
                      str(Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"),
                      str(Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe"),
                      str(Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Google/Chrome/Application/chrome.exe"),
                      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
        executable = next((path for path in candidates if path and Path(path).is_file()), None)
        if not executable:
            raise RuntimeError("Google Chrome is required for blocked pages. Install Chrome, or use --no-browser.")
        self.profile.mkdir(parents=True, exist_ok=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        endpoint = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen([executable, f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1", f"--user-data-dir={self.profile.resolve()}",
            "--no-first-run", "--no-default-browser-check", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                requests.get(endpoint + "/json/version", timeout=1).raise_for_status()
                break
            except requests.RequestException:
                time.sleep(0.25)
        else:
            raise RuntimeError("Could not connect to downloader Chrome. Close any previous downloader window and retry.")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(endpoint, timeout=self.timeout * 1000)
        self.context = self.browser.contexts[0]
        self.page = self.context.new_page()
        self.session.headers["User-Agent"] = self.page.evaluate("navigator.userAgent")
        print("Using downloader Chrome. Complete any verification/age/terms prompts yourself in its window.", flush=True)

    def get(self, url, *, force_browser=False):
        if not force_browser:
            try:
                with self.session.get(url, timeout=self.timeout) as response:
                    challenge = "just a moment" in response.text[:2000].lower() or response.status_code in {401, 403, 429}
                    age_gate = 'id="age-check"' in response.text or "id='age-check'" in response.text
                    if not challenge and not age_gate:
                        response.raise_for_status()
                        return response.text
            finally:
                # This client is sequential. Enhanced 3.0.0 leaks its throttle
                # counter on exceptions; don't let one failure deadlock a batch.
                self.session.current_concurrent_requests = 0
        if not self.allow_browser:
            raise RuntimeError("Site requires browser access. Run again without --no-browser to use Chrome.")
        if not self.page:
            self.start_browser()
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
        deadline = time.monotonic() + self.browser_wait
        while time.monotonic() < deadline:
            title = self.page.title().lower()
            blocked = any(text in title for text in ("just a moment", "attention required", "verify you are human"))
            gate = any(self.page.locator(selector).is_visible() for selector in ("#age-check", "#advanced-av"))
            if not blocked and not gate:
                if response and response.status >= 400 and not self.page.locator("#video, h1").count():
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                html = self.page.content()
                for cookie in self.context.cookies([url]):
                    self.session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"])
                return html
            self.page.wait_for_timeout(500)
        raise RuntimeError(f"Browser verification was not completed within {self.browser_wait}s; rerun when ready")

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.playwright:
                self.playwright.stop()
            if self.process and self.process.poll() is None:
                self.process.terminate()
            self.session.close()


def extract_video(html, url):
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".video_removed, #video_removed"):
        raise ValueError("This video has been removed")
    streams = {}
    match = re.search(r"\b(?:var|let|const)\s+stream_data\s*=\s*(\{.*?\})\s*;", html, re.S)
    if match:
        try:
            streams = json.loads(match[1])
        except json.JSONDecodeError:
            try:
                streams = ast.literal_eval(match[1])
            except (SyntaxError, ValueError):
                pass
    if not isinstance(streams, dict):
        streams = {}
    formats = []
    for quality, values in streams.items():
        if not re.fullmatch(r"\d+p|[248]k", quality, re.I):
            continue
        height = int(quality[:-1]) * (540 if quality.lower().endswith("k") else 1)
        for value in values if isinstance(values, list) else [values]:
            if isinstance(value, str) and value.startswith(("https://", "http://")):
                formats.append({"url": value, "format_id": quality, "height": height, "ext": "mp4"})
    if not formats:
        # Ignore unrelated previews and ads, which also use video tags.
        for source in soup.select("video#main_video_player source[src], #main_video_player_html5_api source[src], video#main_video_player[src]"):
            formats.append({"url": urljoin(url, source["src"]), "format_id": "source", "ext": "mp4"})
    if not formats:
        raise ValueError("No downloadable video streams found on the page")
    title = soup.select_one('[data-testid="video-title"], h1')
    title = title.get_text(" ", strip=True) if title else (soup.title.get_text(strip=True) if soup.title else video_id(url))
    uploader = soup.select_one('#video a[href*="/profile/"], .video_toolbar a.ul, a.ul[href]')
    uploader_name = None
    if uploader:
        uploader_name = uploader.get_text(" ", strip=True)
        if not uploader_name or uploader_name == "None":
            uploader_name = uploader.get("href", "").strip("/").split("/")[-1]
    thumbnail = soup.select_one('meta[property="og:image"]')
    cover = streams.get("cover_image") or (thumbnail.get("content") if thumbnail else None)
    return {"id": video_id(url), "title": title, "uploader": uploader_name or "Unknown",
            "webpage_url": url, "extractor_key": "SpankBang", "extractor": "spankbang",
            "thumbnail": cover, "formats": formats}


def collect_collection(client, url, max_pages=1000):
    videos, visited, title = {}, set(), None
    specific_page = "/profile/" in urlsplit(url).path and "page=" in urlsplit(url).query
    for _ in range(max_pages):
        if url in visited:
            break
        visited.add(url)
        soup = BeautifulSoup(client.get(url), "html.parser")
        if title is None:
            heading = soup.select_one('h1, [data-testid="playlist-title"]')
            title = heading.get_text(" ", strip=True) if heading else urlsplit(url).path.strip("/").replace("/", "-")
        listing = soup.select_one('.video-list-with-ads, .video-list, #video_list, [data-testid="video-list"], main') or soup
        before = len(videos)
        for anchor in listing.select('a[href]'):
            try:
                candidate = normalize_url(urljoin(url, anchor["href"]))
            except ValueError:
                continue
            identity = video_id(candidate)
            if identity:
                videos[identity] = f"https://spankbang.com/{identity}/video/"
        next_link = soup.select_one('a[rel~="next"], li.next a, a.next, a[data-testid="pagination-next"]')
        if specific_page or not next_link or len(videos) == before:
            break
        url = normalize_url(urljoin(url, next_link["href"]))
    else:
        raise RuntimeError(f"Stopped at {max_pages} collection pages; increase --max-pages if intended")
    if not videos:
        raise ValueError("No video links found in the collection")
    return title, list(videos.values())


def download_video(info, client, output):
    options = {"outtmpl": str(output / "%(uploader|Unknown)s - %(title).100B [%(id)s] %(format_id)s.%(ext)s"),
               "format": "best[ext=mp4]/best", "windowsfilenames": True, "writethumbnail": True,
               "continuedl": True, "overwrites": False, "retries": 3, "fragment_retries": 3,
               "socket_timeout": client.timeout,
               "http_headers": {"User-Agent": client.session.headers["User-Agent"], "Referer": info["webpage_url"]}}
    with YoutubeDL(options) as downloader:
        for cookie in client.session.cookies:
            downloader.cookiejar.set_cookie(cookie)
        for index, candidate in enumerate(sorted(info["formats"], key=lambda f: f.get("height", 0), reverse=True)):
            try:
                # Quality in the filename prevents resuming one quality's bytes
                # into a different quality when falling back.
                return downloader.process_ie_result({**info, "formats": [candidate]}, download=True)
            except DownloadError:
                if index == len(info["formats"]) - 1:
                    raise
                print("Trying the next available quality...", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("input.txt"))
    parser.add_argument("-o", "--output", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="Extract metadata without downloading or changing history")
    parser.add_argument("--no-browser", action="store_true", help="Fail clearly when direct HTTP access is blocked")
    parser.add_argument("--browser", action="store_true", help="Use downloader Chrome from the start")
    parser.add_argument("--browser-wait", type=int, default=180, help="Seconds to wait for manual browser verification")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--history", type=Path, help="Override completed-download history path")
    args = parser.parse_args(argv)
    if min(args.timeout, args.browser_wait, args.max_pages) < 1 or (args.browser and args.no_browser):
        parser.error("Timeouts/max-pages must be positive; --browser and --no-browser are mutually exclusive")
    try:
        urls = read_urls(args.source)
        history = args.history if args.history is not None else history_path()
        completed = set()
        for old in read_urls(history) if history.exists() else []:
            try:
                completed.add(url_key(normalize_url(old)))
            except ValueError:
                continue
    except (OSError, ValueError) as error:
        parser.error(str(error))
    client = PageClient(timeout=args.timeout, browser=not args.no_browser, browser_wait=args.browser_wait)
    failed, downloaded, skipped, exported, checked = [], 0, 0, 0, 0
    try:
        for index, raw_url in enumerate(urls, 1):
            print(f"[{index}/{len(urls)}] {raw_url}", flush=True)
            try:
                url = normalize_url(raw_url)
                identity = video_id(url)
                if identity and url_key(url) in completed:
                    print("Already downloaded; skipping.", flush=True)
                    skipped += 1
                    continue
                if not identity:
                    if not re.search(r"/(profile|channel|playlist)/", url):
                        raise ValueError("Expected a video, profile, channel, or playlist URL")
                    if args.browser and not client.page:
                        client.start_browser()
                    title, links = collect_collection(client, url, args.max_pages)
                    if not args.check:
                        args.output.mkdir(parents=True, exist_ok=True)
                        path = args.output / (safe_name(title) + "_videos.txt")
                        path.write_text("\n".join(links) + "\n", encoding="utf-8")
                        print(f"Exported {len(links)} URLs to {path}")
                    else:
                        print(f"Found {len(links)} collection URLs")
                    exported += 1
                    continue
                html = client.get(url, force_browser=args.browser)
                try:
                    info = extract_video(html, url)
                except ValueError:
                    if client.page or args.no_browser:
                        raise
                    info = extract_video(client.get(url, force_browser=True), url)
                print(f"Found {info['title']}: {len(info['formats'])} quality options", flush=True)
                if args.check:
                    checked += 1
                    continue
                args.output.mkdir(parents=True, exist_ok=True)
                download_video(info, client, args.output)
                history.parent.mkdir(parents=True, exist_ok=True)
                with history.open("a", encoding="utf-8") as handle:
                    handle.write("\n" + url + "\n")
                completed.add(url_key(url))
                downloaded += 1
            except (OSError, ValueError, RuntimeError, requests.RequestException, DownloadError, BrowserError) as error:
                failed.append(raw_url)
                print(f"FAILED: {error}", file=sys.stderr, flush=True)
    finally:
        client.close()
    if failed and not args.check:
        args.output.mkdir(parents=True, exist_ok=True)
        failure_path = args.output / "failed_dl.txt"
        existing = read_urls(failure_path) if failure_path.exists() else []
        failure_path.write_text("\n".join(dict.fromkeys(existing + failed)) + "\n", encoding="utf-8")
    print(f"Done: {downloaded} downloaded, {skipped} skipped, {exported} collections, {checked} checked, {len(failed)} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled. Partial downloads can be resumed on the next run.", file=sys.stderr)
        sys.exit(130)
