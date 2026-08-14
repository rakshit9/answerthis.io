"""Disk cache + rate limiting for external API calls.

Every OpenAlex / Semantic Scholar response is cached on disk (JSON, keyed
by a hash of the request). This keeps the demo reproducible, spares the
free-tier rate limits, and makes the API boundary visible: a cache hit and
a live call return byte-identical structures. Failures are NEVER cached.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from ..config import settings

DEFAULT_TTL_S = 7 * 24 * 3600


class ApiError(Exception):
    """Honest failure of an external call — surfaced, never swallowed."""

    def __init__(self, api: str, message: str, status: int | None = None):
        self.api = api
        self.status = status
        super().__init__(f"[{api}] {message}")


class RateLimiter:
    def __init__(self, min_interval_s: float):
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval_s:
            time.sleep(self.min_interval_s - delta)
        self._last = time.monotonic()


def _cache_path(api: str, key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:32]
    d = settings.cache_dir / api
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def cached_get(api: str, url: str, params: dict[str, Any],
               headers: dict[str, str] | None = None,
               limiter: Optional[RateLimiter] = None,
               ttl_s: int = DEFAULT_TTL_S,
               max_retries: int = 3) -> dict:
    """GET with disk cache, client-side rate limiting and 429/5xx backoff.

    Raises ``ApiError`` on definitive failure — callers surface it to the
    user instead of pretending the search returned nothing.
    """
    key = json.dumps({"url": url, "params": params}, sort_keys=True)
    path = _cache_path(api, key)
    if path.exists():
        try:
            blob = json.loads(path.read_text())
            if time.time() - blob.get("_cached_at", 0) < ttl_s:
                return blob["data"]
        except Exception:
            path.unlink(missing_ok=True)

    delay = 1.5
    last_err: Exception | None = None
    for attempt in range(max_retries):
        if limiter:
            limiter.wait()
        try:
            resp = httpx.get(url, params=params, headers=headers or {},
                             timeout=settings.http_timeout_s, follow_redirects=True)
        except httpx.HTTPError as e:
            last_err = e
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 200:
            data = resp.json()
            path.write_text(json.dumps({"_cached_at": time.time(), "data": data}))
            return data
        if resp.status_code in (429, 500, 502, 503):
            retry_after = resp.headers.get("retry-after")
            wait_s = float(retry_after) if retry_after and retry_after.isdigit() else delay
            time.sleep(min(wait_s, 30))
            delay *= 2
            last_err = ApiError(api, f"HTTP {resp.status_code} (rate limited or busy)",
                                resp.status_code)
            continue
        if resp.status_code == 404:
            raise ApiError(api, "not found (404)", 404)
        raise ApiError(api, f"HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code)

    if isinstance(last_err, ApiError):
        raise last_err
    raise ApiError(api, f"request failed after {max_retries} attempts: {last_err}")
