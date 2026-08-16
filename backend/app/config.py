"""Application configuration, read from environment variables.

Every external dependency (LLM provider, Semantic Scholar key, OpenAlex
politeness e-mail) is optional; the app degrades honestly instead of
failing when one is missing.
"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Read ``KEY=VALUE`` lines from ``backend/.env`` into the environment.

    Deliberately tiny and dependency-free — this is the only thing the app
    needs from python-dotenv. A real environment variable always wins, so
    ``OPENAI_API_KEY=… uvicorn …`` still overrides the file; the file is the
    convenience, not the authority.

    Until this existed the backend read plain ``os.environ`` only, which made
    writing a ``.env`` file look like it worked while doing nothing at all.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BACKEND_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class Settings:
    # --- storage -------------------------------------------------------
    data_dir: Path = Path(_env("PIA_DATA_DIR", str(BACKEND_ROOT / "data")))
    cache_dir: Path = Path(_env("PIA_CACHE_DIR", str(BACKEND_ROOT / "data" / "_api_cache")))

    # --- LLM providers (pluggable) ------------------------------------
    # PIA_LLM_PROVIDER: "openai" | "gemini" | "auto" (auto = first provider
    # with a key configured, preferring openai).
    llm_provider: str = _env("PIA_LLM_PROVIDER", "auto")
    openai_api_key: str = _env("OPENAI_API_KEY")
    openai_model: str = _env("PIA_OPENAI_MODEL", "gpt-4o-mini")
    gemini_api_key: str = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    gemini_model: str = _env("PIA_GEMINI_MODEL", "gemini-flash-latest")

    # --- academic search ----------------------------------------------
    semantic_scholar_api_key: str = _env("S2_API_KEY")
    # OpenAlex asks for a mailto to put you in the "polite pool".
    openalex_mailto: str = _env("OPENALEX_MAILTO", "paper-improvement-agent@example.com")

    # --- behaviour -----------------------------------------------------
    # Cap external searches per review run (rate-limit friendliness).
    # Minimum wall-clock seconds an upload's parse takes end-to-end, padded
    # across the stages. Off by default: the pipeline finishes a 24-page
    # paper in a few seconds and the stage view keeps up, so padding it only
    # makes the app feel slow. Set it (e.g. 12) to slow the narration down
    # for a demo or a walkthrough recording.
    parse_min_seconds: float = float(_env("PIA_PARSE_MIN_SECONDS", "0"))
    max_queries_per_review: int = int(_env("PIA_MAX_QUERIES_PER_REVIEW", "10"))
    max_claim_checks_per_review: int = int(_env("PIA_MAX_CLAIM_CHECKS", "12"))
    http_timeout_s: float = float(_env("PIA_HTTP_TIMEOUT", "20"))
    # Retries per external GET on transient 429/5xx. Raise this when running
    # against the *shared* (unauthenticated) Semantic Scholar pool, where a
    # single request often needs several attempts to get through.
    http_max_retries: int = int(_env("PIA_HTTP_MAX_RETRIES", "3"))
    # Upper bound on a single backoff sleep. The shared S2 pool frees up in
    # seconds, so many short retries beat few long ones; an explicit
    # Retry-After from the server is still honored up to this cap.
    http_backoff_cap_s: float = float(_env("PIA_HTTP_BACKOFF_CAP", "10"))

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
