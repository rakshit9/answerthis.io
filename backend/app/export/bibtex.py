"""CSL-JSON → BibTeX serializer (secondary export artifact).

The canonical model stays CSL-JSON and the canonical formatting path is
citeproc + .csl styles; the .bib file is provided as a convenience for
users with an existing BibTeX toolchain.
"""
from __future__ import annotations

CSL_TO_BIBTEX_TYPE = {
    "article-journal": "article",
    "paper-conference": "inproceedings",
    "chapter": "incollection",
    "book": "book",
    "thesis": "phdthesis",
    "report": "techreport",
    "article": "misc",           # preprints
}


def _esc(s: str) -> str:
    return (s.replace("\\", r"\textbackslash{}").replace("&", r"\&")
             .replace("%", r"\%").replace("#", r"\#").replace("_", r"\_"))


def entry_to_bibtex(item: dict) -> str:
    btype = CSL_TO_BIBTEX_TYPE.get(item.get("type", ""), "misc")
    key = item.get("id", "unknown")
    fields: list[tuple[str, str]] = []
    if item.get("title"):
        fields.append(("title", "{" + _esc(item["title"]) + "}"))
    authors = item.get("author") or []
    if authors:
        names = " and ".join(
            (f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
             if isinstance(a, dict) else str(a))
            for a in authors)
        fields.append(("author", "{" + _esc(names) + "}"))
    issued = item.get("issued", {}).get("date-parts", [[None]])
    if issued and issued[0] and issued[0][0]:
        fields.append(("year", "{" + str(issued[0][0]) + "}"))
    container = item.get("container-title")
    if container:
        fieldname = "booktitle" if btype == "inproceedings" else "journal"
        fields.append((fieldname, "{" + _esc(container) + "}"))
    for csl_f, bib_f in (("volume", "volume"), ("page", "pages"),
                         ("DOI", "doi"), ("URL", "url"), ("note", "note")):
        if item.get(csl_f):
            val = str(item[csl_f])
            fields.append((bib_f, "{" + (_esc(val) if bib_f != "url" else val) + "}"))
    body = ",\n".join(f"  {k} = {v}" for k, v in fields)
    return f"@{btype}{{{key},\n{body}\n}}"


def bibliography_to_bibtex(items: list[dict]) -> str:
    return "\n\n".join(entry_to_bibtex(i) for i in items) + "\n"
