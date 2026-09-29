"""Looks up exam dates for a professor's courses straight from the indexed
finki-hub session schedules.

A schedule chunk is a list of records like
    [10.09.2026 11:30-17:30 200ц, лаб. 117: Оперативни системи / Operating systems]
so instead of vector-searching each course (and hoping the model does it for every
course), we parse the records and match course names directly.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.core.retrieval import SearchResult
from backend.models import Chunk, Document

_RECORD_RE = re.compile(r"\[(\d{1,2}\.\d{1,2}\.\d{4}) (\S+) ([^\]]*?): ([^\]]+)\]")
_YEAR_RE = re.compile(r"\d{4}/\d{4}")
# Session names differ from course titles sometimes ("Електронска и мобилна комерција
# (трговија)" vs "Електронска и мобилна трговија"), so names only need to mostly overlap.
NAME_MATCH_THRESHOLD = 0.75


@dataclass
class ExamRecord:
    date: str
    time: str
    rooms: str
    course: str


def parse_exam_records(chunk_text: str) -> list[ExamRecord]:
    return [ExamRecord(*m.groups()) for m in _RECORD_RE.finditer(chunk_text)]


def _name_words(name: str) -> set[str]:
    name = name.split(" / ")[0]  # drop the English translation
    return {w for w in re.findall(r"[^\W\d_]+", name.lower()) if len(w) > 2}


def course_matches(course: str, record_course: str) -> bool:
    a, b = _name_words(course), _name_words(record_course)
    return bool(a) and len(a & b) / len(a | b) >= NAME_MATCH_THRESHOLD


def course_matches_loosely(query: str, record_course: str) -> bool:
    """For names a user typed: every word just has to start like a word in the record
    ("веб програмирање" finds "Веб програмирање", "мрежи" finds all network courses)."""
    query_words = _name_words(query)
    record_words = _name_words(record_course)
    return bool(query_words) and all(any(r.startswith(q[:5]) for r in record_words) for q in query_words)


def pick_sessions(titles: list[str], session: str) -> list[str]:
    """Filters session titles ("2025/2026 Септември", "2025/2026 Летен - Втор Колоквиум")
    by a loose description like "септемвриска" or "втор колоквиум". Words are compared
    by their first 3 letters, so "јунска" matches "Јуни". Returns all titles when the
    description doesn't match anything."""
    words = [w[:3] for w in session.lower().split() if len(w) >= 3 and not _YEAR_RE.fullmatch(w)]

    def hits(title: str) -> int:
        title_words = {w[:3] for w in title.lower().split()}
        return sum(w in title_words for w in words)

    best = max((hits(t) for t in titles), default=0)
    return [t for t in titles if hits(t) == best] if best else titles


def find_exam_dates(
    db: Session,
    courses: list[str],
    session: str = "",
    collected: list[SearchResult] | None = None,
    loose: bool = False,
) -> list[dict]:
    """Exam dates for each course in one academic year - the one named in `session`
    ("2024/2025"), or the latest one we have. Chunks that had a match are added to
    `collected` so the answer can cite them. `loose` is for names typed by a user."""
    matches = course_matches_loosely if loose else course_matches
    year_match = _YEAR_RE.search(session)
    year = year_match.group(0) if year_match else _latest_academic_year(db)
    if year is None:
        return [{"course": c, "exams": []} for c in courses]

    rows = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.source == "finki_hub", Document.type == "schedule", Document.title.startswith(year))
        .all()
    )
    wanted = set(pick_sessions(sorted({doc.title for _, doc in rows}), session))

    found: dict[str, list[dict]] = {c: [] for c in courses}
    for chunk, doc in rows:
        if doc.title not in wanted:
            continue
        chunk_used = False
        for record in parse_exam_records(chunk.text):
            for course in courses:
                if matches(course, record.course):
                    found[course].append(
                        {
                            "session": doc.title,
                            "course_in_schedule": record.course,
                            "date": record.date,
                            "time": record.time,
                            "rooms": record.rooms,
                        }
                    )
                    chunk_used = True
        if chunk_used and collected is not None:
            collected.append(_to_search_result(chunk, doc))

    for exams in found.values():
        exams.sort(key=lambda e: [int(x) for x in reversed(e["date"].split("."))])
    return [{"course": c, "exams": exams} for c, exams in found.items()]


def _latest_academic_year(db: Session) -> str | None:
    titles = db.query(Document.title).filter(Document.source == "finki_hub", Document.type == "schedule").all()
    years = [m.group(0) for (title,) in titles if (m := _YEAR_RE.match(title))]
    return max(years, default=None)


def _to_search_result(chunk: Chunk, doc: Document) -> SearchResult:
    return SearchResult(
        document_id=str(doc.id),
        title=doc.title,
        url=doc.url,
        source=doc.source,
        type=doc.type,
        published_at=doc.published_at,
        chunk_text=chunk.text,
        score=0.0,  # not from vector search
        metadata=doc.doc_metadata or {},
    )
