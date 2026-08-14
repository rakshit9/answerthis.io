"""OpenAlex client (no API key needed). https://docs.openalex.org

Returns ``ExternalSource`` objects whose CSL-JSON is built ONLY from the
API response — this is the no-hallucination boundary: if it isn't in the
response, it isn't in the source.
"""
from __future__ import annotations

from typing import Any, Optional

from ..config import settings
from ..models.findings import ExternalSource
from .cache import ApiError, RateLimiter, cached_get

BASE = "https://api.openalex.org"
_limiter = RateLimiter(0.25)


def _headers() -> dict[str, str]:
    return {"User-Agent": f"paper-improvement-agent (mailto:{settings.openalex_mailto})"}


def _reconstruct_abstract(inv: dict[str, list[int]] | None) -> Optional[str]:
    if not inv:
        return None
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)) or None


def _to_source(w: dict[str, Any]) -> ExternalSource:
    doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
    year = w.get("publication_year")
    authors = [a.get("author", {}).get("display_name", "")
               for a in (w.get("authorships") or [])][:25]
    venue = None
    loc = w.get("primary_location") or {}
    if loc.get("source"):
        venue = loc["source"].get("display_name")
    url = w.get("id") or (f"https://doi.org/{doi}" if doi else "")
    return ExternalSource(
        api="openalex",
        api_id=w.get("id", ""),
        title=w.get("display_name") or w.get("title") or "(untitled)",
        year=year,
        authors=[a for a in authors if a],
        venue=venue,
        doi=doi,
        url=url,
        abstract=_reconstruct_abstract(w.get("abstract_inverted_index")),
        cited_by_count=w.get("cited_by_count"),
        csl=_to_csl(w, doi, year, venue),
    )


def _to_csl(w: dict[str, Any], doi: str | None, year: int | None,
            venue: str | None) -> dict:
    item: dict[str, Any] = {
        "id": w.get("id", "openalex-work"),
        "type": {"journal-article": "article-journal", "proceedings-article": "paper-conference",
                 "book-chapter": "chapter", "book": "book", "posted-content": "article",
                 "preprint": "article", "report": "report",
                 "dissertation": "thesis"}.get(w.get("type_crossref") or w.get("type", ""), "article"),
        "title": w.get("display_name") or w.get("title") or "",
    }
    authors = []
    for a in (w.get("authorships") or [])[:25]:
        name = a.get("author", {}).get("display_name", "")
        if not name:
            continue
        parts = name.rsplit(" ", 1)
        if len(parts) == 2:
            authors.append({"family": parts[1], "given": parts[0]})
        else:
            authors.append({"family": name})
    if authors:
        item["author"] = authors
    if year:
        item["issued"] = {"date-parts": [[year]]}
    if venue:
        item["container-title"] = venue
    if doi:
        item["DOI"] = doi
    if w.get("id"):
        item["URL"] = w["id"]
    bib = w.get("biblio") or {}
    if bib.get("first_page") and bib.get("last_page"):
        item["page"] = f"{bib['first_page']}-{bib['last_page']}"
    if bib.get("volume"):
        item["volume"] = bib["volume"]
    return item


def search(query: str, per_page: int = 10) -> list[ExternalSource]:
    """Relevance-ranked full-text search over titles+abstracts."""
    data = cached_get(
        "openalex", f"{BASE}/works",
        {"search": query, "per-page": per_page, "mailto": settings.openalex_mailto,
         "select": "id,display_name,title,publication_year,doi,authorships,"
                   "primary_location,abstract_inverted_index,cited_by_count,"
                   "type,type_crossref,biblio"},
        headers=_headers(), limiter=_limiter)
    return [_to_source(w) for w in data.get("results", [])]


def by_doi(doi: str) -> Optional[ExternalSource]:
    doi = doi.lower().strip().removeprefix("https://doi.org/")
    try:
        data = cached_get("openalex", f"{BASE}/works/https://doi.org/{doi}",
                          {"mailto": settings.openalex_mailto},
                          headers=_headers(), limiter=_limiter)
    except ApiError as e:
        if e.status == 404:
            return None
        raise
    return _to_source(data)


def by_title(title: str, per_page: int = 5) -> list[ExternalSource]:
    """Title-targeted search used for reference resolution."""
    data = cached_get(
        "openalex", f"{BASE}/works",
        {"filter": f"title.search:{_sanitize_filter(title)}", "per-page": per_page,
         "mailto": settings.openalex_mailto,
         "select": "id,display_name,title,publication_year,doi,authorships,"
                   "primary_location,abstract_inverted_index,cited_by_count,"
                   "type,type_crossref,biblio"},
        headers=_headers(), limiter=_limiter)
    return [_to_source(w) for w in data.get("results", [])]


def _sanitize_filter(s: str) -> str:
    # commas separate filters in the OpenAlex API; colons separate key/value
    return s.replace(",", " ").replace(":", " ").strip()[:300]
