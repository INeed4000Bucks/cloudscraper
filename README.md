# SpankBang Downloader

[![Enhanced cloudscraper version](https://img.shields.io/badge/cloudscraper--enhanced-3.0.0-blue)](https://pypi.org/project/cloudscraper-enhanced/3.0.0/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![image](https://img.shields.io/pypi/pyversions/cloudscraper.svg)](https://pypi.org/project/cloudscraper/)
[![Donate](https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-brightgreen.svg)](https://www.buymeacoffee.com/venomous)



# Installation

Install Python 3.10 or newer and Google Chrome, then run from this repository:

```powershell
python -m pip install -r requirements.txt
```

The downloader uses the bundled **cloudscraper-enhanced 3.0.0** first, Beautiful
Soup for page parsing, yt-dlp for resumable downloads, and Playwright for Chrome
fallback. It uses your installed Chrome; no separate browser download is needed.
The local `cloudscraper` directory contains the actual 3.0.0 release, so it cannot
silently shadow an installed upgrade with the former 1.2.69 implementation.

Alternatively, install the application with `python -m pip install .` and use
`sb-scraper source.txt`. On macOS/Linux, use `python3` where appropriate; a
virtual environment avoids needing elevated privileges or system-package overrides.

# Dependencies

- Python 3.10 or newer and Google Chrome
- **[Requests](https://github.com/kennethreitz/requests)** >= 2.31.0
- **[requests_toolbelt](https://pypi.org/project/requests-toolbelt/)** >= 1.0.0
- Beautiful Soup >= 4.12, yt-dlp >= 2026.10.26, Playwright >= 1.55

The remaining enhanced-library dependencies are in `requirements.txt`.
The app disables automatic 403/session refresh because that feature can stall
inside 3.0.0. Normal challenge handling stays enabled. Blocked pages use Chrome
unless `--no-browser` is supplied. Release provenance is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

# Usage
Put one video, playlist, channel, or profile URL on each line of a UTF-8 text
file. Blank lines and lines beginning with `#` are ignored.

```powershell
python sb_scraper.py source.txt
```

`sb_scraper.py source.txt` also works when Windows has a Python file association.
Without an argument, it reads `input.txt`. Downloads go into the current working
directory. To choose a different directory:

```powershell
python sb_scraper.py source.txt -o downloads
```

When direct HTTP requests are blocked, a separate downloader Chrome window opens.
Complete any age, terms, or verification prompts yourself. The application waits
up to three minutes by default and saves that browser profile for later runs.
It does not use your everyday Chrome profile. Avoid running multiple downloader
instances against the same profile simultaneously.

Useful options:

- `--check`: check metadata/collection links without downloading or modifying download history.
- `--browser`: use Chrome immediately.
- `--no-browser`: report blocked requests without opening Chrome.
- `--browser-wait 300`: allow five minutes for manual verification.
- `--history PATH`: use a different completed-download history file.
- `--max-pages 1000`: limit collection pagination.

Video URLs download the best available MP4 and a cover image. A persistent
download failure tries the next quality. Profile, channel, and playlist URLs
export a deduplicated `*_videos.txt` file; feed that file back into the script to
download its videos. Profile URLs with an explicit `?page=N` export that page only.

# Features
- Partial media downloads resume on the next run. Each quality uses its own file
  so fallback cannot mix bytes from different resolutions.
- Existing `config.txt` / `ALREADY_DL_TXT` settings and legacy URL history are
  respected. On Windows the default history is `%APPDATA%\CB_DL\already_dl.txt`.
- Downloaded videos are identified by exact video ID, including country-domain
  and playlist-link variants, rather than comparing URL prefixes.
- Only completed downloads enter history. Failures are saved to `failed_dl.txt`
  in the output directory and the batch continues. A failed batch returns exit code 1.
- Missing uploader names or old HTML elements do not prevent downloads.
- Collection pagination follows actual next-page links and stops on repeated pages.

Run the downloader regression tests without network access:

```powershell
python -m unittest test_sb_scraper -v
```
