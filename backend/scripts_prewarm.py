"""Dev helper: patiently warm the API disk cache for the demo paper.

Retries resolution + searches in rounds with long sleeps, so transient
free-tier windows get captured into the cache. Safe to run repeatedly.
(Not part of the app; lives outside the package on purpose.)
"""
import sys
import time

from app import store
from app.external import openalex, semantic_scholar
from app.external.cache import ApiError
from app.external.resolve import resolve_reference
from app.models.core import ResolutionStatus

paper_id = sys.argv[1]
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 12
SLEEP_BETWEEN_ROUNDS = 180

QUERIES = [
    "sequence transduction recurrent neural networks",
    "attention mechanism machine translation",
    "self-attention transformer architecture",
    "neural machine translation encoder decoder",
    "positional encoding sequence models",
]

for rnd in range(ROUNDS):
    doc = store.load_paper(paper_id)
    todo = [r for r in doc.references
            if r.resolution.status in (ResolutionStatus.NOT_ATTEMPTED,
                                       ResolutionStatus.FAILED,
                                       ResolutionStatus.UNRESOLVED)]
    print(f"[round {rnd}] {len(todo)} references to (re)try", flush=True)
    ok = 0
    for ref in todo:
        # reset failed status so resolve retries
        if ref.resolution.status != ResolutionStatus.NOT_ATTEMPTED:
            from app.models.core import Resolution
            ref.resolution = Resolution()
        resolve_reference(ref)
        if ref.resolution.status == ResolutionStatus.RESOLVED:
            ok += 1
        time.sleep(2.0)
    store.save_paper(doc)
    resolved_total = sum(1 for r in doc.references
                        if r.resolution.status == ResolutionStatus.RESOLVED)
    print(f"[round {rnd}] +{ok} resolved this round; total {resolved_total}/"
          f"{len(doc.references)}", flush=True)

    for q in QUERIES:
        for name, fn in (("openalex", openalex.search),
                         ("s2", semantic_scholar.search)):
            try:
                res = fn(q, 8)
                print(f"[round {rnd}] {name} '{q[:30]}' -> {len(res)}", flush=True)
            except ApiError as e:
                print(f"[round {rnd}] {name} '{q[:30]}' FAIL {e}", flush=True)
            time.sleep(2.0)

    if resolved_total == len(doc.references):
        print("all resolved; stopping early", flush=True)
        break
    time.sleep(SLEEP_BETWEEN_ROUNDS)
print("prewarm done", flush=True)
