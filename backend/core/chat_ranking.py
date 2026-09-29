"""Re-ranks search results before they go into the chat context.

Vector similarity can't tell this year's exam schedule or announcement from last
year's copy, so we drop old years and add a small recency bonus when sorting. The
bonus is only used for ordering - `score` stays the raw cosine similarity.
"""

import re
from datetime import datetime, timezone

from backend.core.retrieval import RECENCY_MATCH_BOOST, SearchResult

# Extra bonus for schedule chunks dated close to today, fading out over the horizon.
# Smaller than the year bonus - it only breaks ties between sessions of the same year.
SCHEDULE_DATE_BOOST = 0.08
SCHEDULE_DATE_HORIZON_DAYS = 180

_ACADEMIC_YEAR_RE = re.compile(r"^(\d{4})/(\d{4})")
_SCHEDULE_CHUNK_DATE_RE = re.compile(r"\[(\d{1,2})\.(\d{1,2})\.(\d{4})")  # "[10.09.2026 ..."


def effective_year(r: SearchResult) -> int | None:
    """Year of a result, or None when recency doesn't matter for it (courses, bios,
    theses...). Old PDF exam sessions have no date, so we use the 2nd year of "2021/2022"."""
    if r.type == "thesis":
        return None  # an older thesis is still a valid answer
    if r.published_at is not None:
        return r.published_at.year
    if r.type == "schedule":
        m = _ACADEMIC_YEAR_RE.match(r.metadata.get("academic_year", ""))
        if m:
            return int(m.group(2))
    return None


def schedule_chunk_date(chunk_text: str) -> datetime | None:
    m = _SCHEDULE_CHUNK_DATE_RE.search(chunk_text)
    if m is None:
        return None
    day, month, year = (int(g) for g in m.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def recency_bonus(r: SearchResult, current_year: int, now: datetime) -> float:
    bonus = RECENCY_MATCH_BOOST if effective_year(r) == current_year else 0.0
    if r.type == "schedule":
        chunk_date = schedule_chunk_date(r.chunk_text)
        if chunk_date is not None:
            days_away = abs((now.replace(tzinfo=None) - chunk_date).days)
            bonus += SCHEDULE_DATE_BOOST * max(0.0, 1 - days_away / SCHEDULE_DATE_HORIZON_DAYS)
    return bonus


def prefer_current_year(
    results: list[SearchResult], k: int, current_year: int, now: datetime | None = None
) -> list[SearchResult]:
    """Drops older-year results if there's anything from this year, then sorts by
    score + recency bonus and keeps the top k. Undated results are always kept."""
    now = now or datetime.now(timezone.utc)

    if any(effective_year(r) == current_year for r in results):
        results = [r for r in results if effective_year(r) in (None, current_year)]

    def rank(r: SearchResult) -> float:
        return min(1.0, r.score + recency_bonus(r, current_year, now))

    return sorted(results, key=rank, reverse=True)[:k]
