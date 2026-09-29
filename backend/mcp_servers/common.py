"""Shared helpers for the MCP servers - each tool is a filtered `search()`."""

from backend.core.retrieval import SearchResult, search
from backend.db import SessionLocal


def result_to_dict(r: SearchResult) -> dict:
    return {
        "title": r.title,
        "url": r.url,
        "type": r.type,
        "published_at": r.published_at.isoformat() if r.published_at else None,
        "excerpt": r.chunk_text,
        "score": round(r.score, 4),
    }


def run_search(query: str, k: int, source: str, type: str | None = None) -> list[dict]:
    with SessionLocal() as db:
        results = search(db, query, k=k, source=source, type=type, recency_boost=True)
    return [result_to_dict(r) for r in results]
