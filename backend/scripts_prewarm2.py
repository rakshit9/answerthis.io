"""Dev helper v2: fast S2-focused cache warming for the demo paper.

While the sandbox IP's OpenAlex daily budget is exhausted, skip OpenAlex
entirely (instant ApiError) and cycle quick single-attempt S2 calls in many
short rounds — shared-pool 429 gaps are caught by frequency, not patience.
"""
import functools
import sys
import time

from app import store
from app.external import cache, openalex, resolve, semantic_scholar
from app.external.cache import ApiError
from app.models.core import Resolution, ResolutionStatus

paper_id = sys.argv[1]
MINUTES = int(sys.argv[2]) if len(sys.argv) > 2 else 45

# 1-attempt requests
fast_get = functools.partial(cache.cached_get, max_retries=1)
semantic_scholar.cached_get = fast_get

# OpenAlex is budget-dead from this IP right now: fail instantly, honestly.
def _oa_dead(*a, **k):
    raise ApiError("openalex", "skipped by prewarm (daily budget exhausted from this IP)")
openalex.search = _oa_dead
openalex.by_doi = _oa_dead
openalex.by_title = _oa_dead
resolve.openalex = openalex

QUERIES = [
    "sequence transduction recurrent neural networks",
    "attention mechanism neural machine translation",
    "self-attention transformer architecture",
    "encoder decoder neural machine translation",
    "positional encoding sequence models",
    "multi-head attention representation learning",
]

deadline = time.time() + MINUTES * 60
rnd = 0
while time.time() < deadline:
    doc = store.load_paper(paper_id)
    todo = [r for r in doc.references
            if r.resolution.status != ResolutionStatus.RESOLVED]
    if not todo:
        print("all references resolved!", flush=True)
        break
    got = 0
    for ref in todo:
        ref.resolution = Resolution()
        resolve.resolve_reference(ref)
        if ref.resolution.status == ResolutionStatus.RESOLVED:
            got += 1
        time.sleep(1.5)
    store.save_paper(doc)
    total = sum(1 for r in doc.references
                if r.resolution.status == ResolutionStatus.RESOLVED)
    print(f"[round {rnd}] +{got}, total {total}/{len(doc.references)}", flush=True)

    for q in QUERIES:
        try:
            res = semantic_scholar.search(q, 8)
            print(f"[round {rnd}] s2 search '{q[:34]}' -> {len(res)}", flush=True)
        except ApiError:
            pass
        time.sleep(1.5)
    rnd += 1
    time.sleep(45)
print("prewarm2 done", flush=True)
