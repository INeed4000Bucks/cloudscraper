# Bundled cloudscraper release

The `cloudscraper/` package is copied from the published
[`cloudscraper-enhanced` 3.0.0 wheel](https://pypi.org/project/cloudscraper-enhanced/3.0.0/),
maintained by VeNoMouS and Zied Boughdir under the MIT license. The original
copyright and permission notice are retained in `LICENSE`.

- Artifact: `cloudscraper_enhanced-3.0.0-py3-none-any.whl`
- SHA-256: `9dede333b40c716e422604fa34dd6ed00940c6492cf8c45a2e5606dcec3c98ad`
- All 27 package files were copied unchanged and checked against PyPI's published digest.

The downloader configures this release with automatic 403 refresh disabled and
no timed session refresh, since that upstream path can recursively enter its own
request handler. It also removes the concurrency gate for its sequential session,
so a nested challenge request cannot wait forever on the outer request, and resets
the request counter after each page request so failures cannot block the batch.
These adjustments are in `sb_scraper.py`; the bundled library files are unchanged.
