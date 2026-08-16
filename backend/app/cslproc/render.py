"""CSL rendering: canonical CSL-JSON items + a .csl style → formatted
in-text labels and bibliography. All citation formatting flows through
citeproc-py and the vendored CSL style files — no hand-rolled citation
string templates anywhere in the app.

Known citeproc-py limitation, handled here: ``suppress-author`` is ignored,
so narrative (``[[citet:…]]``) labels in author-year styles are derived
from the parenthetical label by stripping the leading author names (the
name already sits in the prose).
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

from citeproc import (Citation, CitationItem, CitationStylesBibliography,
                      CitationStylesStyle, formatter)
from citeproc.source.json import CiteProcJSON

from ..models.core import CITE_TOKEN_RE, PaperDocument, Reference

STYLES_DIR = Path(__file__).parent / "styles"

# styles whose in-text form is author-year (needed for citet handling)
AUTHOR_YEAR_STYLES = {"apa", "chicago-author-date", "harvard-cite-them-right"}


def list_styles() -> list[dict]:
    out = []
    for p in sorted(STYLES_DIR.glob("*.csl")):
        m = re.search(r"<title>([^<]+)</title>", p.read_text()[:4000])
        out.append({"id": p.stem, "title": m.group(1).strip() if m else p.stem})
    return out


def style_path(style_id: str) -> Path:
    p = STYLES_DIR / f"{style_id}.csl"
    if not p.exists():
        raise ValueError(f"Unknown CSL style: {style_id!r}. "
                         f"Available: {[s['id'] for s in list_styles()]}")
    return p


RENDERABLE_MIN_CONF = 0.5


def renderable(ref: Reference) -> bool:
    """Only refs with enough structure go through citeproc; the rest are
    shown with their raw text (honest fallback, still in the bibliography)."""
    return bool(ref.csl.get("title")) and (
        ref.parse_confidence >= RENDERABLE_MIN_CONF
        or ref.resolution.status.value == "resolved"
        or ref.added_by != "pdf_parse")


class DocumentRenderer:
    """Renders one document's citations in one style.

    Citation groups are registered in document order, so numeric styles
    number by first appearance; the bibliography order is whatever the CSL
    style dictates (appearance for IEEE, alphabetical for APA…).
    """

    def __init__(self, doc: PaperDocument, style_id: str | None = None,
                 html: bool = False):
        self.doc = doc
        self.style_id = style_id or doc.csl_style
        self.author_year = self.style_id in AUTHOR_YEAR_STYLES
        self._fmt = formatter.html if html else formatter.plain
        self._labels: dict[tuple[str, ...], str] = {}
        self._bib_entries: list[tuple[str, str]] = []
        self._skipped: list[Reference] = []
        self._build()

    # -- public ---------------------------------------------------------
    def label_for(self, ref_ids: list[str], narrative: bool = False) -> str:
        label = self._labels.get(tuple(ref_ids))
        if label is None:
            # group not registered (e.g. token added after build) — rebuild
            self._build(extra_groups=[tuple(ref_ids)])
            label = self._labels.get(tuple(ref_ids), "[?]")
        if narrative and self.author_year:
            return _strip_authors_from_label(label)
        return label

    def render_text(self, token_text: str) -> str:
        def repl(m: re.Match) -> str:
            narrative = m.group(1) == "t"
            ids = [r.strip() for r in m.group(2).split(",") if r.strip()]
            return self.label_for(ids, narrative)
        return CITE_TOKEN_RE.sub(repl, token_text)

    def render_paragraphs(self, token_text: str) -> list[list[dict]]:
        """The same rendering as :meth:`render_text`, but keeping the join
        between a label and the references it stands for.

        Returns paragraphs of parts: ``{"t": "prose"}`` for text and
        ``{"label": "(Smith, 2020)", "refs": ["ref_3"]}`` for a citation.
        The reader needs the ref ids to link a label to its bibliography
        entry, and handing the client structured parts keeps citation
        formatting inside citeproc — the alternative, emitting HTML and
        re-parsing it in the browser, would put a second citation renderer
        in the frontend, which is exactly what this module exists to avoid.
        """
        paragraphs: list[list[dict]] = []
        for para in token_text.split("\n\n"):
            parts: list[dict] = []
            pos = 0
            for m in CITE_TOKEN_RE.finditer(para):
                if m.start() > pos:
                    parts.append({"t": para[pos:m.start()]})
                ids = [r.strip() for r in m.group(2).split(",") if r.strip()]
                parts.append({"label": self.label_for(ids, m.group(1) == "t"),
                              "refs": ids})
                pos = m.end()
            if pos < len(para):
                parts.append({"t": para[pos:]})
            paragraphs.append(parts)
        return paragraphs

    def bibliography(self) -> list[dict]:
        """[{ref_id, formatted, raw_fallback}] in style order; refs that
        couldn't be rendered come last with their raw text."""
        out = [{"ref_id": rid, "formatted": text, "raw_fallback": False}
               for rid, text in self._bib_entries]
        for ref in self._skipped:
            out.append({"ref_id": ref.id, "formatted": ref.raw_text,
                        "raw_fallback": True})
        return out

    # -- internals ------------------------------------------------------
    def _build(self, extra_groups: list[tuple[str, ...]] | None = None) -> None:
        refs = {r.id: r for r in self.doc.references}
        items = [r.csl | {"id": r.id} for r in self.doc.references if renderable(r)]
        self._skipped = [r for r in self.doc.references if not renderable(r)]
        renderable_ids = {i["id"] for i in items}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            style = CitationStylesStyle(str(style_path(self.style_id)), validate=False)
            source = CiteProcJSON(items)
            bib = CitationStylesBibliography(style, source, self._fmt)

            # Bibliography ordering: citeproc-py does not apply the style's
            # <sort> — it emits items in registration order. So:
            #  * author-year styles: pre-register EVERY renderable item in
            #    alphabetical (family, year, title) order → sorted bibliography;
            #  * numeric styles: register in first-appearance order, which is
            #    exactly what drives the citation numbers.
            if self.author_year:
                def sort_key(item: dict):
                    fam = ""
                    if item.get("author"):
                        fam = (item["author"][0].get("family") or "").lower()
                    dp = item.get("issued", {}).get("date-parts", [[None]])
                    year = dp[0][0] if dp and dp[0] and dp[0][0] else 9999
                    return (fam or "￿", year, str(item.get("title", "")).lower())
                for item in sorted(items, key=sort_key):
                    bib.register(Citation([CitationItem(item["id"])]))

            # groups in document order
            groups: list[tuple[str, ...]] = []
            seen = set()
            for sec in self.doc.sections:
                for m in CITE_TOKEN_RE.finditer(sec.content):
                    ids = tuple(r.strip() for r in m.group(2).split(",") if r.strip())
                    if ids not in seen:
                        seen.add(ids)
                        groups.append(ids)
            for g in (extra_groups or []):
                if g not in seen:
                    groups.append(g)
                    seen.add(g)

            registered: list[tuple[tuple[str, ...], Citation]] = []
            for g in groups:
                usable = [i for i in g if i in renderable_ids]
                if not usable:
                    self._labels[g] = "[" + ",".join(
                        refs[i].label or i for i in g if i in refs) + "]"
                    continue
                cit = Citation([CitationItem(i) for i in usable])
                bib.register(cit)
                registered.append((g, cit))

            # numeric styles: append uncited-but-renderable refs at the end
            cited_ids = {i for g, _ in registered for i in g}
            if not self.author_year:
                for item in items:
                    if item["id"] not in cited_ids:
                        bib.register(Citation([CitationItem(item["id"])]))

            for g, cit in registered:
                self._labels[g] = str(bib.cite(cit, _noop_warn))

            self._bib_entries = []
            for cit_item, entry in zip(bib.items, bib.bibliography()):
                self._bib_entries.append((str(cit_item.key), str(entry)))
            # de-duplicate (bib.items may repeat keys across citations)
            seen_keys: set[str] = set()
            deduped = []
            for k, t in self._bib_entries:
                if k not in seen_keys:
                    seen_keys.add(k)
                    deduped.append((k, t))
            self._bib_entries = deduped


def _noop_warn(_item) -> None:
    return None


def _strip_authors_from_label(label: str) -> str:
    """'(Vaswani et al., 2017)' → '(2017)'; '(Smith 2020a; …)' → '(2020a)'.
    Used for narrative citations in author-year styles because the author
    name already appears in the running text."""
    m = re.match(r"^\((.*)\)$", label.strip())
    if not m:
        return label
    inner = m.group(1)
    years = re.findall(r"\b(\d{4}[a-z]?)\b", inner)
    if not years:
        return label
    return "(" + ", ".join(years) + ")"
