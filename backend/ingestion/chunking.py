"""Splits documents into chunks for embedding. Word count stands in for token count."""

import re

DEFAULT_MAX_WORDS = 220
DEFAULT_OVERLAP_WORDS = 40

# Schedules list ~150-190 courses per session, so they get much smaller chunks -
# otherwise one chunk mixes ~20 courses and matches every course query equally badly.
SCHEDULE_MAX_WORDS = 50
SCHEDULE_OVERLAP_WORDS = 10

_BRACKETED_RECORD_RE = re.compile(r"\[[^\[\]]*\]")
_RECORD_LEADING_TOKEN_RE = re.compile(r"\[(\S+)")


def chunk_text(text: str, max_words: int = DEFAULT_MAX_WORDS, overlap_words: int = DEFAULT_OVERLAP_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= max_words:
        return [" ".join(words)]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap_words
    return chunks


def _pack_records_to_budget(records: list[str], max_words: int) -> list[str]:
    """Joins whole records into chunks of up to `max_words`, never splitting a record."""
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for record in records:
        record_words = len(record.split())
        if current and current_words + record_words > max_words:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
        current.append(record)
        current_words += record_words
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_schedule_by_date(text: str) -> list[str]:
    """One chunk per exam day (more if the day is long), built from the
    "[date time room: course]" records, with the session name on top of each chunk.
    Old PDF sessions have no such records and fall back to small word chunks."""
    records = _BRACKETED_RECORD_RE.findall(text)
    if not records:
        return chunk_text(text, max_words=SCHEDULE_MAX_WORDS, overlap_words=SCHEDULE_OVERLAP_WORDS)

    preamble_end = text.find("[")
    preamble = text[:preamble_end].strip()
    # e.g. "2025/2026 Јуни" - so "јунска сесија" queries can match the day chunks
    session_label = preamble.splitlines()[0] if preamble else ""

    grouped: dict[str, list[str]] = {}
    for record in records:
        match = _RECORD_LEADING_TOKEN_RE.match(record)
        key = match.group(1) if match else "?"
        grouped.setdefault(key, []).append(record)

    chunks: list[str] = []
    for day_records in grouped.values():
        for day_chunk in _pack_records_to_budget(day_records, SCHEDULE_MAX_WORDS):
            chunks.append(f"{session_label}\n{day_chunk}" if session_label else day_chunk)
    if preamble:
        chunks.insert(0, preamble)
    return chunks


def get_chunks(doc_type: str, text: str) -> list[str]:
    if doc_type == "schedule":
        return chunk_schedule_by_date(text)
    return chunk_text(text)
