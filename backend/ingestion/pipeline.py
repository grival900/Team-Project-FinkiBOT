import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from backend.core.site_settings import get_bool_setting
from backend.db import SessionLocal
from backend.ingestion.chunking import get_chunks
from backend.ingestion.embeddings import embed_texts
from backend.models import Chunk, Document
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.registry import SCRAPERS

logger = logging.getLogger(__name__)

_ingestion_lock = threading.Lock()

Outcome = Literal["new", "updated", "unchanged"]

ProgressCallback = Callable[[int, int, str | None], None]


@dataclass
class ScraperStats:
    seen: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0


def upsert_document(db: Session, ndoc: NormalizedDocument) -> tuple[Document, Outcome]:
    """Insert or update a document by URL. "unchanged" means we can skip re-embedding."""
    existing = db.query(Document).filter_by(url=ndoc.url).one_or_none()

    if existing is not None and (existing.source != ndoc.source or existing.type != ndoc.type):
        # two scrapers producing the same URL is a bug - don't let one overwrite the other
        raise ValueError(
            f"URL collision on {ndoc.url!r}: already indexed as "
            f"{existing.source}/{existing.type}, but {ndoc.source}/{ndoc.type} scraper "
            f"produced the same URL"
        )

    if existing is None:
        # Same title and content under a new URL = the page moved (happened when the
        # site left Drupal). The title check matters: some announcements share the
        # same body text but are different events.
        moved = (
            db.query(Document)
            .filter_by(source=ndoc.source, type=ndoc.type, title=ndoc.title, content_hash=ndoc.content_hash)
            .first()
        )
        if moved is not None:
            moved.url = ndoc.url
            moved.published_at = ndoc.published_at
            moved.doc_metadata = ndoc.metadata
            return moved, "unchanged"

        doc = Document(
            source=ndoc.source,
            type=ndoc.type,
            title=ndoc.title,
            url=ndoc.url,
            published_at=ndoc.published_at,
            content=ndoc.content,
            content_hash=ndoc.content_hash,
            doc_metadata=ndoc.metadata,
        )
        db.add(doc)
        db.flush()
        return doc, "new"

    if existing.content_hash == ndoc.content_hash:
        # still refresh the cheap fields in case a scraper started filling them in
        existing.published_at = ndoc.published_at
        existing.doc_metadata = ndoc.metadata
        return existing, "unchanged"

    existing.title = ndoc.title
    existing.content = ndoc.content
    existing.content_hash = ndoc.content_hash
    existing.published_at = ndoc.published_at
    existing.doc_metadata = ndoc.metadata
    return existing, "updated"


def reindex_document(db: Session, doc: Document) -> None:
    texts = get_chunks(doc.type, doc.content)
    replace_chunks(db, doc, texts, embed_texts(texts))


def replace_chunks(db: Session, doc: Document, texts: list[str], vectors: list) -> None:
    """Swaps a document's chunks for new ones (also used by the seed, which ships vectors)."""
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    for i, (text, vector) in enumerate(zip(texts, vectors)):
        db.add(Chunk(document_id=doc.id, chunk_index=i, text=text, embedding=vector))


def ingest_normalized_document(db: Session, ndoc: NormalizedDocument) -> tuple[Document, Outcome]:
    doc, outcome = upsert_document(db, ndoc)
    if outcome != "unchanged":
        reindex_document(db, doc)
    return doc, outcome


def run_ingestion(
    cadence: str | None = None,
    progress_cb: ProgressCallback | None = None,
    incremental: bool = False,
    name: str | None = None,
) -> dict[str, ScraperStats]:
    """Runs the enabled scrapers and returns counts per scraper.

    - `cadence`: only "frequent" or "slow" scrapers (None = all)
    - `name`: just one scraper, e.g. "finki_hub.sessions"
    - `incremental`: skip URLs we already have (faster, but misses edited pages)
    - `progress_cb(done, total, current)`: drives the admin progress bar

    Only one ingestion runs at a time; a second call returns {} right away."""
    if name is not None and name not in {entry.name for entry in SCRAPERS}:
        raise ValueError(f"Unknown scraper name: {name!r} (see backend/scrapers/registry.py for valid names)")
    if not _ingestion_lock.acquire(blocking=False):
        logger.warning("Skipping ingestion — another ingestion is already running")
        return {}
    try:
        return _run_ingestion_locked(cadence, progress_cb, incremental, name)
    finally:
        _ingestion_lock.release()


def run_full_ingestion(incremental: bool = False) -> dict[str, ScraperStats]:
    """All scrapers - slow, meant for a manual full rebuild."""
    return run_ingestion(cadence=None, incremental=incremental)


def run_frequent_ingestion(incremental: bool = False) -> dict[str, ScraperStats]:
    """Announcements and the finki-hub JSON feeds - cheap, runs hourly."""
    return run_ingestion(cadence="frequent", incremental=incremental)


def run_slow_ingestion(incremental: bool = False) -> dict[str, ScraperStats]:
    """Syllabi, professor profiles, recordings - one request per page, runs weekly."""
    return run_ingestion(cadence="slow", incremental=incremental)


def _known_urls_by_source(db: Session) -> dict[str, set[str]]:
    """{source: set of URLs we already have}"""
    known: dict[str, set[str]] = {}
    for source, url in db.query(Document.source, Document.url):
        known.setdefault(source, set()).add(url)
    return known


def _run_ingestion_locked(
    cadence: str | None,
    progress_cb: ProgressCallback | None = None,
    incremental: bool = False,
    name: str | None = None,
) -> dict[str, ScraperStats]:
    stats: dict[str, ScraperStats] = {}
    with SessionLocal() as db:
        # the admin panel can switch off a broken scraper without a redeploy
        active = [
            entry
            for entry in SCRAPERS
            if entry.enabled
            and get_bool_setting(db, f"scraper_enabled:{entry.name}", True)
            and (cadence is None or entry.cadence == cadence)
            and (name is None or entry.name == name)
        ]
        total = len(active)
        known = _known_urls_by_source(db) if incremental else {}

        for done, entry in enumerate(active):
            if progress_cb is not None:
                progress_cb(done, total, entry.name)
            s = ScraperStats()
            skip_urls = known.get(entry.source, set()) if incremental else None
            try:
                for ndoc in entry.fn(skip_urls=skip_urls):
                    try:
                        with db.begin_nested():
                            _, outcome = ingest_normalized_document(db, ndoc)
                    except Exception:
                        logger.exception("Failed to ingest %s (%s)", ndoc.url, entry.name)
                        s.failed += 1
                        continue
                    s.seen += 1
                    if outcome == "new":
                        s.new += 1
                    elif outcome == "updated":
                        s.updated += 1
                    else:
                        s.unchanged += 1
                    if s.seen % 20 == 0:
                        db.commit()
                db.commit()
            except Exception:
                logger.exception("Scraper %s failed", entry.name)
                db.rollback()
            stats[entry.name] = s

        if progress_cb is not None:
            progress_cb(total, total, None)
    return stats
