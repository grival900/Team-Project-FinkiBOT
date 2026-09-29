"""One-off cleanup of duplicate documents: `python -m backend.scripts.dedupe_documents [--dry-run]`.

Documents with the same source, type, title and content under different URLs are
the same thing indexed twice (from when the site moved off Drupal). Keeps one per
group - preferring the current /announcements/ URL - and deletes the rest. Safe to re-run.
"""

import sys

from sqlalchemy import func, select

from backend.db import SessionLocal
from backend.models import Document

CURRENT_PATH_MARKER = "/announcements/"


def _pick_canonical(docs: list[Document]) -> Document:
    for doc in docs:
        if CURRENT_PATH_MARKER in doc.url:
            return doc
    return min(docs, key=lambda d: d.scraped_at)


def find_duplicate_groups(db) -> list[list[Document]]:
    dupe_keys = (
        db.query(Document.source, Document.type, Document.title, Document.content_hash)
        .group_by(Document.source, Document.type, Document.title, Document.content_hash)
        .having(func.count(Document.id) > 1)
        .all()
    )
    groups = []
    for source, type_, title, content_hash in dupe_keys:
        stmt = select(Document).filter_by(source=source, type=type_, title=title, content_hash=content_hash)
        groups.append(list(db.execute(stmt).scalars().all()))
    return groups


def dedupe(dry_run: bool = False) -> int:
    removed = 0
    with SessionLocal() as db:
        for group in find_duplicate_groups(db):
            canonical = _pick_canonical(group)
            for doc in group:
                if doc.id == canonical.id:
                    continue
                print(f"  duplicate of {canonical.url!r}: removing {doc.url!r} ({doc.title!r})")
                if not dry_run:
                    db.delete(doc)
                removed += 1
        if not dry_run:
            db.commit()
    return removed


def find_superseded_subject_docs(db) -> list[Document]:
    """Old-accreditation syllabus pages (e.g. the 2018 one when 2023 exists) that stay
    indexed because scrapers never delete. Only flags a page when a current page with
    the same title exists, so we never remove a course's only syllabus."""
    current_urls = {
        (metadata or {}).get("official_subject_url")
        for (metadata,) in db.query(Document.doc_metadata).filter(
            Document.source == "finki_hub", Document.type == "course"
        )
    }
    current_urls.discard(None)

    docs = db.query(Document).filter(Document.source == "official", Document.type == "course").all()
    current_titles = {d.title for d in docs if d.url in current_urls}

    return [d for d in docs if d.url not in current_urls and d.title in current_titles]


def dedupe_superseded_subjects(dry_run: bool = False) -> int:
    removed = 0
    with SessionLocal() as db:
        for doc in find_superseded_subject_docs(db):
            print(f"  superseded subject page: removing {doc.url!r} ({doc.title!r})")
            if not dry_run:
                db.delete(doc)
            removed += 1
        if not dry_run:
            db.commit()
    return removed


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    n_dupes = dedupe(dry_run=dry_run)
    n_superseded = dedupe_superseded_subjects(dry_run=dry_run)
    verb = "Would remove" if dry_run else "Removed"
    print(f"{verb} {n_dupes} duplicate document(s) and {n_superseded} superseded subject page(s).")
