"""HTTP client behavior: retry budget, quota fast-fail, cache semantics."""
import json

import httpx
import pytest

from app.external import cache
from app.external.cache import ApiError, cached_get


class FakeResp:
    def __init__(self, status_code, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_quota_exhausted_fails_immediately(monkeypatch, tmp_path):
    monkeypatch.setattr(cache.settings, "cache_dir", tmp_path)
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return FakeResp(429, text='{"error":"Rate limit exceeded",'
                                  '"message":"Insufficient budget. This request cost..."}')
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(cache.time, "sleep", lambda s: None)

    with pytest.raises(ApiError) as ei:
        cached_get("openalex", "https://api.openalex.org/works", {"q": "x"}, max_retries=10)
    assert ei.value.exhausted is True
    assert len(calls) == 1               # no pointless retries on a spent budget


def test_transient_429_is_retried_then_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(cache.settings, "cache_dir", tmp_path)
    seq = [FakeResp(429, text="too many requests, slow down"),
           FakeResp(429, text="too many requests, slow down"),
           FakeResp(200, {"ok": True})]
    monkeypatch.setattr(httpx, "get", lambda url, **kw: seq.pop(0))
    monkeypatch.setattr(cache.time, "sleep", lambda s: None)

    out = cached_get("semantic_scholar", "https://api.s2.org/search", {"q": "x"},
                     max_retries=5)
    assert out == {"ok": True}
    assert seq == []


def test_retry_budget_comes_from_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(cache.settings, "cache_dir", tmp_path)
    monkeypatch.setattr(cache.settings, "http_max_retries", 4)
    calls = []

    def fake_get(url, **kw):
        calls.append(1)
        return FakeResp(429, text="slow down")
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(cache.time, "sleep", lambda s: None)

    with pytest.raises(ApiError):
        cached_get("semantic_scholar", "https://api.s2.org/search", {"q": "x"})
    assert len(calls) == 4               # honors PIA_HTTP_MAX_RETRIES


def test_success_is_cached_failure_is_not(monkeypatch, tmp_path):
    monkeypatch.setattr(cache.settings, "cache_dir", tmp_path)
    n = {"calls": 0}

    def fake_get(url, **kw):
        n["calls"] += 1
        return FakeResp(200, {"v": n["calls"]})
    monkeypatch.setattr(httpx, "get", fake_get)

    a = cached_get("openalex", "https://api.openalex.org/works", {"q": "y"})
    b = cached_get("openalex", "https://api.openalex.org/works", {"q": "y"})
    assert a == b == {"v": 1}
    assert n["calls"] == 1               # second call served from disk cache

    # a failing request must not create a cache entry
    monkeypatch.setattr(httpx, "get", lambda url, **kw: FakeResp(429, text="slow down"))
    monkeypatch.setattr(cache.time, "sleep", lambda s: None)
    with pytest.raises(ApiError):
        cached_get("openalex", "https://api.openalex.org/works", {"q": "z"}, max_retries=2)
    monkeypatch.setattr(httpx, "get", lambda url, **kw: FakeResp(200, {"fresh": True}))
    assert cached_get("openalex", "https://api.openalex.org/works", {"q": "z"}) == {"fresh": True}
