"""FastAPI application entry point.

Run:  uvicorn app.main:app --reload   (from backend/)
Serves the built frontend from ../frontend/dist when present.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes_actions import router as actions_router
from .api.routes_papers import router as papers_router

app = FastAPI(title="Paper Improvement Agent",
              description="Upload a paper, get a grounded peer review, "
                          "edit it agentically — citations kept intact.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers_router)
app.include_router(actions_router)

_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
