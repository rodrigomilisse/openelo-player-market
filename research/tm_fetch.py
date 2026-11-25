"""Polite, cached page fetcher for transfermarkt.com (research use only, see tm_recent.py).

One request at a time, at least MIN_INTERVAL seconds apart, exponential back-off on
429/5xx, and a hard stop after repeated blocks: if the site starts refusing us we stop
and tell the owner, we never rotate addresses or disguise the client.

Every page is written to the cache before it is parsed. A cached page is never fetched
again unless the caller asks (`refetch=True`), so a killed run resumes where it stopped.
"""

import gzip
import time
from pathlib import Path

import requests

BASE_URL = "https://www.transfermarkt.com"
# Same browser User-Agent as tm_client.py: the site serves a stripped page to unknown clients.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}
MIN_INTERVAL = 3.0          # seconds between the start of two requests (the brief's minimum)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
BACKOFF_SECONDS = 15        # 15, 30, 60, 120, 240
MAX_CONSECUTIVE_BLOCKS = 3  # pages that failed every retry in a row -> stop the run
RETRY_STATUS = {429, 500, 502, 503, 504}


class Blocked(Exception):
    """The site keeps refusing requests. Stop and tell the owner."""


class NotFound(Exception):
    pass


class Fetcher:
    def __init__(self, cache_dir: Path, min_interval: float = MIN_INTERVAL, offline: bool = False):
        self.cache_dir = cache_dir
        self.min_interval = min_interval
        self.offline = offline
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last_request = 0.0
        self._failed_in_a_row = 0
        self.fetched = 0
        self.from_cache = 0

    def cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.html.gz"

    def cached(self, key: str) -> bool:
        return self.cache_path(key).exists()

    def get(self, path: str, key: str, refetch: bool = False) -> str:
        """The page at BASE_URL + path, from the cache under `key` when it is there."""
        target = self.cache_path(key)
        if target.exists() and not refetch:
            self.from_cache += 1
            return gzip.decompress(target.read_bytes()).decode("utf-8")
        if self.offline:
            raise NotFound(f"offline and not cached: {key}")
        text = self._download(BASE_URL + path)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".part")
        partial.write_bytes(gzip.compress(text.encode("utf-8")))
        partial.rename(target)
        self.fetched += 1
        return text

    def _wait(self) -> None:
        pause = self.min_interval - (time.monotonic() - self._last_request)
        if pause > 0:
            time.sleep(pause)
        self._last_request = time.monotonic()

    def _download(self, url: str) -> str:
        last = None
        for attempt in range(MAX_RETRIES):
            self._wait()
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            except requests.RequestException as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    self._failed_in_a_row = 0
                    return response.text
                if response.status_code == 404:
                    self._failed_in_a_row = 0
                    raise NotFound(url)
                if response.status_code not in RETRY_STATUS:
                    raise Blocked(f"HTTP {response.status_code} from {url}; stopping, not retrying")
                last = f"HTTP {response.status_code}"
            wait = BACKOFF_SECONDS * 2 ** attempt
            print(f"  [{last}] {url}: retry {attempt + 1}/{MAX_RETRIES - 1} in {wait}s", flush=True)
            time.sleep(wait)
        self._failed_in_a_row += 1
        if self._failed_in_a_row >= MAX_CONSECUTIVE_BLOCKS:
            raise Blocked(f"{self._failed_in_a_row} pages in a row failed every retry (last: {last} from {url}). "
                          "The site may be blocking this client; stopping. Try again later.")
        raise NotFound(f"gave up on {url} ({last})")
