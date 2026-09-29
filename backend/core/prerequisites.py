"""Turns a course's prerequisite text into links to the prerequisite courses.

The text is course names joined with " или " ("Алгоритми ... или Примена на ..."),
or something else like "100 кредити". Only exact title matches become links.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import Document


def split_prerequisite_text(text: str | None) -> list[str]:
    """Pure parsing step, unit-testable without a DB. Splits comma-separated
    requirements and "или" (or) alternatives into candidate course-name segments."""
    if not text:
        return []
    segments = []
    for part in text.split(","):
        segments.extend(part.split(" или "))
    return [s.strip() for s in segments if s.strip()]


def resolve_prerequisites(db: Session, text: str) -> list[dict]:
    """[{"text": segment, "document_id": id or None}, ...]. Links to finki-hub course
    pages (not syllabi) because those have their own prerequisite links, so the
    student can keep clicking down the chain."""
    results = []
    for segment in split_prerequisite_text(text):
        doc = (
            db.query(Document)
            .filter(
                Document.type == "course",
                Document.source == "finki_hub",
                func.lower(Document.title) == segment.lower(),
            )
            .first()
        )
        results.append({"text": segment, "document_id": str(doc.id) if doc else None})
    return results
