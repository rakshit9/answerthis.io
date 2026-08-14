"""Scripted end-to-end demo on a real paper, capturing screenshots + video.

Usage:  python3 scripts/demo_walkthrough.py <pdf_path> <out_dir>
Needs the backend running on :8000 (with LLM key) and network access to the
academic APIs (or a warmed cache).
"""
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
pdf_path, out_dir = sys.argv[1], Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)


def wait_for(fn, timeout_s=600, every=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        v = fn()
        if v:
            return v
        time.sleep(every)
    raise TimeoutError


def main() -> None:
    # --- upload via API (the UI upload is screenshotted separately) -----
    with open(pdf_path, "rb") as f:
        r = httpx.post(f"{BASE}/api/papers", files={"file": ("paper.pdf", f, "application/pdf")},
                       timeout=120)
    r.raise_for_status()
    pid = r.json()["id"]
    print("paper:", pid, r.json()["title"], flush=True)

    # --- resolve references --------------------------------------------
    httpx.post(f"{BASE}/api/papers/{pid}/resolve", timeout=30)
    wait_for(lambda: httpx.get(f"{BASE}/api/papers/{pid}/resolve/status",
                               timeout=30).json()["done"], timeout_s=900, every=5)
    st = httpx.get(f"{BASE}/api/papers/{pid}/resolve/status", timeout=30).json()
    print("resolution:", st["counts"], flush=True)

    # --- review ---------------------------------------------------------
    run_id = httpx.post(f"{BASE}/api/papers/{pid}/review",
                        json={"missing_work": True, "claim_checks": True},
                        timeout=30).json()["run_id"]

    def review_done():
        d = httpx.get(f"{BASE}/api/papers/{pid}/review/{run_id}", timeout=30).json()
        return d if d["status"] in ("done", "failed") else None
    review = wait_for(review_done, timeout_s=1200, every=5)
    print("review:", review["status"], len(review["findings"]), "findings", flush=True)

    # --- edits ----------------------------------------------------------
    def run_edit(command):
        prop_id = httpx.post(f"{BASE}/api/papers/{pid}/edit",
                             json={"command": command}, timeout=30).json()["proposal_id"]

        def done():
            d = httpx.get(f"{BASE}/api/papers/{pid}/proposals/{prop_id}", timeout=30).json()
            return d if d["status"] != "running" else None
        prop = wait_for(done, timeout_s=600, every=4)
        print("edit:", command, "->", prop["status"],
              len(prop.get("changes", [])), "changes", flush=True)
        return prop

    prop1 = run_edit("add more citations to the introduction")
    if prop1["status"] == "proposed" and prop1["integrity"]["ok"]:
        ids = [c["id"] for c in prop1["changes"]]
        httpx.post(f"{BASE}/api/papers/{pid}/proposals/{prop1['id']}/apply",
                   json={"approved_change_ids": ids}, timeout=60)
        print("applied proposal 1", flush=True)

    # --- browser walkthrough with screenshots + video -------------------
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900},
                            record_video_dir=str(out_dir / "video"),
                            record_video_size={"width": 1440, "height": 900})
        pg = ctx.new_page()

        pg.goto(BASE, wait_until="networkidle")
        pg.screenshot(path=str(out_dir / "01_upload.png"))

        # the SPA has no URL routing; open the paper via the recent list
        pg.click(".recent .card")
        pg.wait_for_selector(".ref-table", timeout=20000)
        time.sleep(1)
        pg.screenshot(path=str(out_dir / "02_parse.png"))
        pg.mouse.wheel(0, 900)
        time.sleep(0.6)
        pg.screenshot(path=str(out_dir / "03_references.png"))

        pg.click("text=2 · Read")
        pg.wait_for_selector(".reader h1", timeout=30000)
        time.sleep(1)
        pg.screenshot(path=str(out_dir / "04_reader.png"))

        pg.click("text=3 · Peer review")
        time.sleep(1.5)
        pg.screenshot(path=str(out_dir / "05_review_log.png"))
        pg.mouse.wheel(0, 1100)
        time.sleep(0.6)
        pg.screenshot(path=str(out_dir / "06_review_findings.png"))
        pg.mouse.wheel(0, 1400)
        time.sleep(0.6)
        pg.screenshot(path=str(out_dir / "07_review_findings2.png"))

        pg.click("text=4 · Edit")
        time.sleep(1.5)
        pg.screenshot(path=str(out_dir / "08_edit_proposal.png"))
        pg.mouse.wheel(0, 1200)
        time.sleep(0.6)
        pg.screenshot(path=str(out_dir / "09_edit_diff.png"))

        # run the shorten command live in the UI for the video
        pg.mouse.wheel(0, -4000)
        pg.fill(".cmd input", "make the introduction shorter")
        pg.click("text=Propose edit")
        try:
            pg.wait_for_selector("text=Proposed changes", timeout=240000)
            time.sleep(1)
            pg.screenshot(path=str(out_dir / "10_edit_shorten.png"))
        except Exception:
            pg.screenshot(path=str(out_dir / "10_edit_shorten_pending.png"))

        pg.click("text=5 · Export")
        pg.wait_for_selector("text=Download LaTeX zip", timeout=15000)
        pg.click("text=Preview main.tex")
        pg.wait_for_selector(".tex-preview", timeout=30000)
        time.sleep(1)
        pg.screenshot(path=str(out_dir / "11_export.png"))

        ctx.close()
        b.close()
    print("walkthrough captured to", out_dir, flush=True)


if __name__ == "__main__":
    main()
