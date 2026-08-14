"""Semantic Scholar Academic Graph client. https://api.semanticscholar.org

Works without a key (shared, slow rate pool); ``S2_API_KEY`` lifts limits.
Same no-hallucination boundary as the OpenAlex client: everything comes
from the API response.
"""
from __future__ import annotations

from typing import Any, Optional

from ..config import settings
from ..models.findings import ExternalSource
from .cache import ApiError, RateLimiter, cached_get

BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = ("title,abstract,year,authors,externalIds,url,venue,citationCount,"
          "publicationTypes,journal")
# unauthenticated pool is roughly 1 rps shared — stay well under
_limiter = RateLimiter(1.1 if not settings.semantic_scholar_api_key else 0.35)


def _headers() -> dict[str, str]:
    h = {"User-Agent": "paper-improvement-agent"}
    if settings.semantic_scholar_api_key:
        h["x-api-key"] = settings.semantic_scholar_api_key
    return h


def _to_source(p: dict[str, Any]) -> ExternalSource:
    ext = p.get("externalIds") or {}
    doi = ext.get("DOI")
    pid = p.get("paperId", "")
    url = p.get("url") or (f"https://www.semanticscholar.org/paper/{pid}" if pid else "")
    return ExternalSource(
        api="semantic_scholar",
        api_id=pid,
        title=p.get("title") or "(untitled)",
        year=p.get("year"),
        authors=[a.get("name", "") for a in (p.get("authors") or [])][:25],
        venue=p.get("venue") or (p.get("journal") or {}).get("name"),
        doi=doi,
        url=url,
        abstract=p.get("abstract"),
        cited_by_count=p.get("citationCount"),
        csl=_to_csl(p, doi),
    )


def _to_csl(p: dict[str, Any], doi: str | None) -> dict:
    types = p.get("publicationTypes") or []
    csl_type = "paper-conference" if "Conference" in types else "article-journal"
    if not p.get("venue") and not p.get("journal"):
        csl_type = "article"
    item: dict[str, Any] = {"id": p.get("paperId", "s2-paper"), "type": csl_type,
                            "title": p.get("title") or ""}
    authors = []
    for a in (p.get("authors") or [])[:25]:
        name = a.get("name", "")
        parts = name.rsplit(" ", 1)
        if len(parts) == 2:
            authors.append({"family": parts[1], "given": parts[0]})
        elif name:
            authors.append({"family": name})
    if authors:
        item["author"] = authors
    if p.get("year"):
        item["issued"] = {"date-parts": [[p["year"]]]}
    venue = p.get("venue") or (p.get("journal") or {}).get("name")
    if venue:
        item["container-title"] = venue
    if doi:
        item["DOI"] = doi
    if p.get("url"):
        item["URL"] = p["url"]
    ext = p.get("externalIds") or {}
    if ext.get("ArXiv"):
        item.setdefault("URL", f"https://arxiv.org/abs/{ext['ArXiv']}")
        item["note"] = f"arXiv:{ext['ArXiv']}"
    return item


def search(query: str, limit: int = 10) -> list[ExternalSource]:
    data = cached_get("semantic_scholar", f"{BASE}/paper/search",
                      {"query": query[:300], "limit": limit, "fields": FIELDS},
                      headers=_headers(), limiter=_limiter)
    return [_to_source(p) for p in data.get("data", [])]


def by_id(paper_id: str) -> Optional[ExternalSource]:
    """paper_id may be 'DOI:10.x/y', 'ARXIV:1706.03762', or an S2 sha."""
    try:
        data = cached_get("semantic_scholar", f"{BASE}/paper/{paper_id}",
                          {"fields": FIELDS}, headers=_headers(), limiter=_limiter)
    except ApiError as e:
        if e.status == 404:
            return None
        raise
    return _to_source(data)


def by_doi(doi: str) -> Optional[ExternalSource]:
    return by_id(f"DOI:{doi.strip().removeprefix('https://doi.org/')}")


def by_arxiv(arxiv_id: str) -> Optional[ExternalSource]:
    return by_id(f"ARXIV:{arxiv_id}")
