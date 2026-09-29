"""Tools the chat model can call to look things up itself.

Each one is a plain function; the Gemini SDK builds the tool schema from the signature
and docstring, so the docstrings below are what the model reads. Every search result
a tool finds is also added to `collected`, so the answer can cite it.
"""

import re
from collections.abc import Callable

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.core.exam_schedule import find_exam_dates
from backend.core.retrieval import SearchResult, search
from backend.core.theses import find_theses, stats_as_source, thesis_statistics, thesis_to_dict
from backend.core.transliteration import is_latin_only, transliterate_latin_to_cyrillic
from backend.mcp_servers.common import result_to_dict
from backend.mcp_servers.official_live_mcp.server import search_official_site_live
from backend.models import Document

# Official-site names start with "д-р"/"м-р" (sometimes "м-р."), finki-hub ones don't.
_ACADEMIC_TITLE_RE = re.compile(r"^(?:д-р|м-р\.?)\s+", re.IGNORECASE)
_COURSES_PER_PROFESSOR_LIMIT = 8


def _to_cyrillic(text: str) -> str:
    return transliterate_latin_to_cyrillic(text) if is_latin_only(text) else text


def _strip_academic_title(name: str) -> str:
    return _ACADEMIC_TITLE_RE.sub("", name).strip()


def find_courses_taught_by(db: Session, professor_name: str, limit: int = _COURSES_PER_PROFESSOR_LIMIT) -> list[dict]:
    """finki-hub courses whose text mentions every part of the name. Matching word by
    word (not the full name) because the two sites sometimes write names differently,
    e.g. "Магдалена Костоска" vs "Магдалена Костоска Ѓорчевска"."""
    tokens = [t for t in _strip_academic_title(professor_name).split() if len(t) > 1]
    if not tokens:
        return []
    rows = (
        db.query(Document)
        .filter(
            Document.source == "finki_hub",
            Document.type == "course",
            and_(*[Document.content.ilike(f"%{t}%") for t in tokens]),
        )
        .limit(limit)
        .all()
    )
    return [{"title": r.title, "url": r.url} for r in rows]


def build_chat_tools(db: Session, min_score: float | None, collected: list[SearchResult]) -> list[Callable]:
    def _run(query: str, limit: int, source: str, doc_type: str) -> list[dict]:
        results = search(db, query, k=limit, source=source, type=doc_type, min_score=min_score, recency_boost=True)
        collected.extend(results)
        return [result_to_dict(r) for r in results]

    def search_announcements(query: str, limit: int = 5) -> list[dict]:
        """Search the official student announcement board (огласна табла): enrollment
        notices, FSS elections, guest lectures, and exam-session schedule postings."""
        return _run(query, limit, "official", "announcement")

    def get_course_info(query: str, limit: int = 5) -> list[dict]:
        """Search official course syllabus pages by name or topic: full syllabus
        text — prerequisites, teacher, ECTS credits, learning objectives, content
        outline, and literature."""
        return _run(query, limit, "official", "course")

    def get_professor_info(query: str, limit: int = 5) -> list[dict]:
        """Search official professor/staff directory pages by name: bio/resume,
        publications, and contact email when filled in."""
        return _run(query, limit, "official", "professor")

    def search_faculty_info(query: str, limit: int = 5) -> list[dict]:
        """Search static faculty info pages: organization/leadership, study
        programs, admissions requirements, international-student info, and contact
        details. Not for announcements, course syllabi, or professor bios."""
        return _run(query, limit, "official", "page")

    def get_exam_schedule_reference(query: str, limit: int = 5) -> list[dict]:
        """Find the official exam-session reference link (finki.ukim.mk) for a
        session by name — title and URL only, the exact per-course dates live in a
        linked spreadsheet this does not parse. Prefer `find_exam_dates_for_course` for
        actual per-course exam dates/times/rooms."""
        return _run(query, limit, "official", "schedule")

    def search_courses(query: str, limit: int = 5) -> list[dict]:
        """Search FINKI courses by name or topic (finki-hub.com): level, semester,
        prerequisites, professors/assistants, and accreditation years/tags."""
        return _run(query, limit, "finki_hub", "course")

    def search_staff(query: str, limit: int = 5) -> list[dict]:
        """Search FINKI teaching staff by name, position, or email (finki-hub.com):
        title, position, cabinet, email, and course portal link."""
        return _run(query, limit, "finki_hub", "staff")

    def search_consultations(query: str, limit: int = 5) -> list[dict]:
        """Search a named professor's scheduled consultation slots: actual
        date/time/room for each upcoming slot, or that none are currently
        scheduled."""
        return _run(query, limit, "finki_hub", "consultation")

    def search_materials(query: str, limit: int = 5) -> list[dict]:
        """Search recorded-lecture links, playlists, and notes shared per course
        (snimki.finki-hub.com) — student-maintained, not comprehensive."""
        return _run(query, limit, "finki_hub", "material")

    def search_exam_sessions(query: str, limit: int = 5) -> list[dict]:
        """Search exam session schedules by session name, academic year, or course
        name (e.g. "Јуни 2025"). Returns the per-course date/time/room extracted from
        the schedule spreadsheets — this is for browsing a whole session; for one
        course's exam use
        `find_exam_dates_for_course`. Raise `limit` (up to ~20) for a broad "the whole
        session's schedule" question."""
        return _run(query, limit, "finki_hub", "schedule")

    def find_courses_taught_by_(professor_name: str, limit: int = _COURSES_PER_PROFESSOR_LIMIT) -> list[dict]:
        """Find every course a named professor or assistant teaches. Use it first for
        questions about a professor's materials or consultations per course, then
        call `search_materials`/etc. once per course found. For a professor's exam
        dates use `find_exam_dates_for_professor` instead."""
        return find_courses_taught_by(db, professor_name, limit)

    find_courses_taught_by_.__name__ = "find_courses_taught_by"

    def find_exam_dates_for_professor(professor_name: str, session: str = "") -> list[dict]:
        """Exam dates/times/rooms for every course a named professor teaches, in one
        call. `session` narrows it down, e.g. "септемвриска", "јунска", "втор
        колоквиум" or an academic year like "2024/2025"; leave it empty for all
        sessions of the current academic year. A course with an empty `exams` list
        has no exam in the matching session(s)."""
        courses = [c["title"] for c in find_courses_taught_by(db, professor_name)]
        return find_exam_dates(db, courses, _to_cyrillic(session), collected)

    def find_exam_dates_for_course(course_name: str, session: str = "") -> list[dict]:
        """Exam dates/times/rooms for one course, read straight from the exam
        schedules. Use this for "when is the exam for <course>" questions. `course_name`
        can be the full or partial Macedonian name (e.g. "Веб програмирање"); every
        schedule entry whose name matches is returned, with its name as written in the
        schedule. `session` works like in `find_exam_dates_for_professor`."""
        return find_exam_dates(db, [_to_cyrillic(course_name)], _to_cyrillic(session), collected, loose=True)

    def search_official_documents(query: str, limit: int = 5) -> list[dict]:
        """Search official documents (PDFs) linked from finki.ukim.mk: rulebooks
        (правилници), statutes, study guides, forms and study program elaborates, e.g.
        rules for doctoral studies or mentors. Use it for questions about rules and
        procedures that the pages themselves only link to."""
        return _run(query, limit, "official", "document")

    def search_theses(topic: str = "", mentor: str = "", limit: int = 5) -> list[dict]:
        """Search bachelor (дипломска) and master (магистерска) theses from
        diplomski.finki-hub.com: title, mentor, committee, status, date and a short
        abstract. Give a `topic` to search by subject, a `mentor` name to list that
        mentor's theses (newest first), or both. `limit` up to 10. `date` is the
        submission date for bachelor theses and the defense date for master theses."""
        found = find_theses(db, _to_cyrillic(topic), _to_cyrillic(mentor), limit, min_score)
        collected.extend(found)
        return [thesis_to_dict(r) for r in found]

    def thesis_stats(mentor: str = "", year: str = "", level: str = "") -> dict:
        """Thesis counts (analytics). With a `mentor` name: how many theses each matching
        professor has mentored - total, bachelor/master, completed/in progress, per
        year - and how many committees they sat on. Without a mentor: overall totals and
        the professors with the most theses. `year` (e.g. "2025") and `level`
        ("bachelor" or "master") narrow it down. Use this for "how many" questions;
        use `search_theses` to list the theses themselves."""
        stats = thesis_statistics(db, _to_cyrillic(mentor), year, level)
        collected.append(stats_as_source(stats))
        return stats

    def live_site_search(query: str, limit: int = 3) -> list[dict]:
        """Search finki.ukim.mk's own live site search (not the local index) — use
        this only when the other tools above found nothing relevant, to check
        whether the official site has something newer than the local index."""
        return search_official_site_live(query, limit=limit)

    return [
        search_announcements,
        get_course_info,
        get_professor_info,
        search_faculty_info,
        get_exam_schedule_reference,
        search_courses,
        search_staff,
        search_consultations,
        search_materials,
        search_exam_sessions,
        find_courses_taught_by_,
        find_exam_dates_for_professor,
        find_exam_dates_for_course,
        search_official_documents,
        search_theses,
        thesis_stats,
        live_site_search,
    ]
