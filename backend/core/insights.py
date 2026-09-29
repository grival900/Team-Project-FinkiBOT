"""Counts for the Insights dashboard. Course stats are computed in Python - there are
only a few hundred courses."""

from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import Document


def count_tags(metadata_list: list[dict], limit: int = 12) -> list[dict]:
    """Pure aggregation step, unit-testable without a DB."""
    counter: Counter = Counter()
    for metadata in metadata_list:
        counter.update(metadata.get("tags", []))
    return [{"tag": tag, "count": count} for tag, count in counter.most_common(limit)]


def count_semesters(metadata_list: list[dict]) -> list[dict]:
    """Pure aggregation step, unit-testable without a DB. Uses each course's most
    recent accreditation only, so a course isn't double-counted across years."""
    counter: Counter = Counter()
    for metadata in metadata_list:
        accreditations = metadata.get("accreditations", [])
        if not accreditations:
            continue
        semester = accreditations[0].get("Семестар")
        if semester:
            counter[semester] += 1

    def sort_key(item: tuple[str, int]) -> tuple[int, object]:
        try:
            return (0, int(item[0]))
        except ValueError:
            return (1, item[0])

    return [{"semester": semester, "count": count} for semester, count in sorted(counter.items(), key=sort_key)]


def documents_by_type(db: Session) -> list[dict]:
    rows = (
        db.query(Document.source, Document.type, func.count(Document.id))
        .group_by(Document.source, Document.type)
        .order_by(Document.source, Document.type)
        .all()
    )
    return [{"source": source, "type": doc_type, "count": count} for source, doc_type, count in rows]


def announcements_by_month(db: Session) -> list[dict]:
    month = func.to_char(Document.published_at, "YYYY-MM")
    rows = (
        db.query(month, func.count(Document.id))
        .filter(Document.type == "announcement", Document.published_at.isnot(None))
        .group_by(month)
        .order_by(month)
        .all()
    )
    return [{"month": m, "count": count} for m, count in rows]


def _finki_hub_course_metadata(db: Session) -> list[dict]:
    rows = db.query(Document.doc_metadata).filter(Document.source == "finki_hub", Document.type == "course").all()
    return [metadata for (metadata,) in rows]


def course_tag_counts(db: Session) -> list[dict]:
    return count_tags(_finki_hub_course_metadata(db))


def course_semester_distribution(db: Session) -> list[dict]:
    return count_semesters(_finki_hub_course_metadata(db))


def build_course_code_options(rows: list[tuple[str, dict]]) -> list[dict]:
    """{code, name} per course (latest accreditation), for the course picker."""
    options = []
    for title, metadata in rows:
        accreditations = (metadata or {}).get("accreditations", [])
        if not accreditations:
            continue
        code = accreditations[0].get("Код")
        if not code:
            continue
        options.append({"code": code, "name": title})
    options.sort(key=lambda o: o["name"])
    return options


def course_code_options(db: Session) -> list[dict]:
    rows = db.query(Document.title, Document.doc_metadata).filter(
        Document.source == "finki_hub", Document.type == "course"
    ).all()
    return build_course_code_options(rows)
