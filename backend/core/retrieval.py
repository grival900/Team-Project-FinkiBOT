"""Vector search over the indexed chunks, used by /search, /chat and the MCP servers."""

import difflib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.transliteration import is_latin_only, transliterate_latin_to_cyrillic
from backend.ingestion.embeddings import embed_query
from backend.models import Chunk, Document

ALL_SOURCES = ["official", "finki_hub"]
# Types searched as their own group, per source: ~4000 thesis abstracts and long
# rulebook PDFs would otherwise fill every result and push out courses, staff and pages.
SEPARATE_TYPES = {"finki_hub": "thesis", "official": "document"}

# Bonus when a short query (a name, a course) is found in the result's title, so the
# page *about* something beats pages that just mention it.
TITLE_MATCH_BOOST = 0.12
_MAX_BOOST_QUERY_TOKENS = 5  # longer queries are topical, not a name lookup
# Fuzzy match per word - transliteration isn't exact ("kalajdziski" -> "калајѕиски").
_TITLE_TOKEN_SIM = 0.82
# Fetch at least this many candidates per source so the boosts have something to reorder.
_RERANK_POOL = 30

# Bonus for recently published results, fading to zero over two years. The faculty
# reposts almost the same announcements every year, and similarity alone can't tell
# this year's copy from an old one. Only used when `recency_boost=True`.
RECENCY_MATCH_BOOST = 0.12
_RECENCY_BOOST_HORIZON_DAYS = 730


@dataclass
class SearchResult:
    document_id: str
    title: str
    url: str
    source: str
    type: str
    published_at: datetime | None
    chunk_text: str
    score: float  # cosine similarity in [-1, 1], higher is more relevant
    metadata: dict[str, Any] = field(default_factory=dict)


def _query_vectors(query: str) -> list[list[float]]:
    """Embeds the query, plus a Cyrillic version if it was typed in latinica
    ("bazi na podatoci"). We search both so words like "SQL" still match."""
    queries = [query]
    if is_latin_only(query):
        translit = transliterate_latin_to_cyrillic(query)
        if translit != query:
            queries.append(translit)
    return [embed_query(q) for q in queries]


def _search_by_vector(
    db: Session,
    query_vector: list[float],
    k: int,
    source: str | None,
    type: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    exclude_type: str | None = None,
) -> list[SearchResult]:
    distance = Chunk.embedding.cosine_distance(query_vector)

    stmt = select(Chunk, Document, distance.label("distance")).join(Document, Chunk.document_id == Document.id)
    if source is not None:
        stmt = stmt.where(Document.source == source)
    if type is not None:
        stmt = stmt.where(Document.type == type)
    if exclude_type is not None:
        stmt = stmt.where(Document.type != exclude_type)
    # note: a date filter leaves out everything undated (courses, professors...)
    if date_from is not None:
        stmt = stmt.where(Document.published_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Document.published_at < date_to + timedelta(days=1))
    stmt = stmt.order_by(distance).limit(k)

    return [
        SearchResult(
            document_id=str(doc.id),
            title=doc.title,
            url=doc.url,
            source=doc.source,
            type=doc.type,
            published_at=doc.published_at,
            chunk_text=chunk.text,
            score=1 - dist,
            metadata=doc.doc_metadata or {},
        )
        for chunk, doc, dist in db.execute(stmt).all()
    ]


def _title_query_variants(query: str) -> list[list[str]]:
    """The query's words (and the Cyrillic version for latinica), if it's short enough."""
    variants = [query.lower().split()]
    if is_latin_only(query):
        variants.append(transliterate_latin_to_cyrillic(query).split())
    return [v for v in variants if 1 <= len(v) <= _MAX_BOOST_QUERY_TOKENS]


def _token_in_title(token: str, title_tokens: list[str]) -> bool:
    return any(
        token in tt or difflib.SequenceMatcher(None, token, tt).ratio() >= _TITLE_TOKEN_SIM
        for tt in title_tokens
    )


def _apply_title_boost(query: str, results: list[SearchResult]) -> None:
    """Adds TITLE_MATCH_BOOST to results whose title contains every query word."""
    variants = _title_query_variants(query)
    if not variants:
        return
    for r in results:
        title_tokens = r.title.lower().split()
        if any(all(_token_in_title(t, title_tokens) for t in variant) for variant in variants):
            r.score = min(1.0, r.score + TITLE_MATCH_BOOST)


def _apply_recency_boost(results: list[SearchResult], now: datetime) -> None:
    """Adds up to RECENCY_MATCH_BOOST: full on the day it's published, zero after the horizon."""
    for r in results:
        if r.published_at is None:
            continue
        published = r.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_days = (now - published).total_seconds() / 86400
        remaining = 1 - age_days / _RECENCY_BOOST_HORIZON_DAYS
        if remaining <= 0:
            continue
        r.score = min(1.0, r.score + RECENCY_MATCH_BOOST * min(remaining, 1.0))


def _merge(results_by_chunk: dict[str, SearchResult], results: list[SearchResult]) -> None:
    for result in results:
        key = f"{result.document_id}:{result.chunk_text[:80]}"
        existing = results_by_chunk.get(key)
        if existing is None or result.score > existing.score:
            results_by_chunk[key] = result


def search(
    db: Session,
    query: str,
    k: int = 5,
    source: str | None = None,
    type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_score: float | None = None,
    recency_boost: bool = False,
) -> list[SearchResult]:
    """Top `k` results per source (and for theses and documents), best first.

    Each source is searched separately and the results merged. With one shared
    ranking, the long official syllabus pages pushed the short finki-hub cards out
    completely (e.g. "bazi" returned 8 official results and 2 finki-hub). So without a
    `source` you get up to k results from each. Theses and documents are groups of
    their own.

    `min_score` drops weak matches. `recency_boost` prefers newer documents.
    """
    vectors = _query_vectors(query)
    now = datetime.now(timezone.utc)

    pool = max(k, _RERANK_POOL)
    results_by_chunk: dict[str, SearchResult] = {}
    for src, doc_type, exclude in _groups(source, type):
        per_source: dict[str, SearchResult] = {}
        for vector in vectors:
            _merge(per_source, _search_by_vector(db, vector, pool, src, doc_type, date_from, date_to, exclude_type=exclude))
        ranked = list(per_source.values())
        _apply_title_boost(query, ranked)
        if recency_boost:
            _apply_recency_boost(ranked, now)
        top_k = sorted(ranked, key=lambda r: r.score, reverse=True)[:k]
        _merge(results_by_chunk, top_k)

    ordered = sorted(results_by_chunk.values(), key=lambda r: r.score, reverse=True)
    if min_score is not None:
        ordered = [r for r in ordered if r.score >= min_score]
    return ordered


def _groups(source: str | None, type: str | None) -> list[tuple[str, str | None, str | None]]:
    """(source, type, excluded type) for each separately ranked group."""
    sources = [source] if source is not None else ALL_SOURCES
    if type is not None:
        return [(src, type, None) for src in sources]
    groups = [(src, None, SEPARATE_TYPES.get(src)) for src in sources]
    groups += [(src, SEPARATE_TYPES[src], None) for src in sources if src in SEPARATE_TYPES]
    return groups
