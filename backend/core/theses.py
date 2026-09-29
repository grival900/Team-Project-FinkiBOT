"""Thesis lookups for the chat: by topic (vector search) and/or by mentor, and counts."""

import json
from collections import Counter

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.core.retrieval import SearchResult, search
from backend.models import Document
from backend.scrapers.finki_hub.thesis_archive import DIPLOMAS_PAGE

# a thesis is ~800 characters; tool results have to fit Groq's 8000 tokens/minute
_EXCERPT_CHARS = 200
MAX_THESES = 10


def mentor_matches(mentor: str, wanted: str) -> bool:
    """Every word of `wanted` appears in the mentor's name ("Чорбев" matches "Иван Чорбев")."""
    name = mentor.lower()
    return all(word in name for word in wanted.lower().split())


def find_theses(
    db: Session, query: str = "", mentor: str = "", limit: int = 5, min_score: float | None = None
) -> list[SearchResult]:
    limit = min(limit, MAX_THESES)
    if query:
        # search wider when we still have to filter by mentor afterwards
        results = search(db, query, k=50 if mentor else limit, source="finki_hub", type="thesis", min_score=min_score)
        if mentor:
            results = [r for r in results if mentor_matches(r.metadata.get("mentor", ""), mentor)]
        return results[:limit]

    if not mentor.split():
        return []
    # newest first; the content filter is just a quick pre-filter, the metadata check decides
    rows = (
        db.query(Document)
        .filter(Document.type == "thesis", and_(*[Document.content.ilike(f"%{w}%") for w in mentor.split()]))
        .order_by(Document.published_at.desc().nulls_last())
        .all()
    )
    matching = [d for d in rows if mentor_matches((d.doc_metadata or {}).get("mentor", ""), mentor)]
    return [_to_result(d) for d in matching[:limit]]


def thesis_to_dict(r: SearchResult) -> dict:
    m = r.metadata
    # the abstract starts after the "Опис:" line; the fields above it are already here
    abstract = r.chunk_text.split("Опис:", 1)[-1].strip()
    return {
        "title": r.title,
        "level": m.get("level"),
        "mentor": m.get("mentor"),
        "status": m.get("status"),
        "date": m.get("date"),
        "abstract": abstract[:_EXCERPT_CHARS],
    }


def _to_result(doc: Document) -> SearchResult:
    return SearchResult(
        document_id=str(doc.id),
        title=doc.title,
        url=doc.url,
        source=doc.source,
        type=doc.type,
        published_at=doc.published_at,
        chunk_text=doc.content,
        score=0.0,  # not from vector search
        metadata=doc.doc_metadata or {},
    )


# --- statistics ------------------------------------------------------------------------

TOP_MENTORS = 10


def is_completed(meta: dict) -> bool:
    """Bachelor theses end at "Одбрана", master theses at step 24 ("... е завршена")."""
    status = meta.get("status", "")
    return status == "Одбрана" if meta.get("level") == "bachelor" else status.startswith("24.")


def _year(meta: dict) -> str:
    return meta.get("date", "")[-4:] or "?"


def _counts(rows: list[dict]) -> dict:
    completed = sum(is_completed(r) for r in rows)
    return {
        "total": len(rows),
        "bachelor": sum(r.get("level") == "bachelor" for r in rows),
        "master": sum(r.get("level") == "master" for r in rows),
        "completed": completed,
        "in_progress": len(rows) - completed,
        "by_year": dict(sorted(Counter(_year(r) for r in rows).items())),
    }


def summarize_theses(rows: list[dict], mentor: str = "", year: str = "", level: str = "") -> dict:
    """Counts over thesis metadata. With `mentor`: per matching mentor, as mentor and as
    committee member. Without: totals and the mentors with the most theses. `year` and
    `level` ("bachelor"/"master") narrow the rows first."""
    if year:
        rows = [r for r in rows if _year(r) == year]
    if level:
        rows = [r for r in rows if r.get("level") == level]

    if not mentor:
        top = Counter(r.get("mentor", "") for r in rows).most_common(TOP_MENTORS)
        return {**_counts(rows), "top_mentors": [{"mentor": m, "theses": n} for m, n in top]}

    names = {r.get("mentor", "") for r in rows} | {c for r in rows for c in r.get("committee", [])}
    matching = sorted(n for n in names if n and mentor_matches(n, mentor))
    return {
        "mentors": [
            {
                "name": name,
                **_counts([r for r in rows if r.get("mentor") == name]),
                "committee_member": sum(name in r.get("committee", []) for r in rows),
            }
            for name in matching
        ]
    }


def thesis_statistics(db: Session, mentor: str = "", year: str = "", level: str = "") -> dict:
    rows = [meta or {} for (meta,) in db.query(Document.doc_metadata).filter(Document.type == "thesis")]
    return summarize_theses(rows, mentor, year, level)


def stats_as_source(stats: dict) -> SearchResult:
    """The statistics as a citable source, so the answer links to the thesis archive
    instead of whatever other document happens to share its numbers."""
    return SearchResult(
        document_id="thesis-statistics",
        title="Статистика за дипломски и магистерски работи",
        url=DIPLOMAS_PAGE,
        source="finki_hub",
        type="thesis",
        published_at=None,
        chunk_text=json.dumps(stats, ensure_ascii=False),
        score=0.0,
    )
