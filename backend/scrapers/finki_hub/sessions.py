import logging
import re
from collections.abc import Iterator
from datetime import datetime

from backend.ingestion.file_extraction import extract_pdf_text, extract_xlsx_schedule_grid
from backend.scrapers.finki_hub.base import SESSIONS_BASE_URL, SESSIONS_JSON_URL
from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"^(\d{4}/\d{4})")


def parse_session_entry(session_name: str, filename: str) -> tuple[str, str, dict]:
    """Pure parsing step, unit-testable. Returns (title, content, metadata)."""
    download_url = f"{SESSIONS_BASE_URL}/{filename}"

    year_match = _YEAR_RE.match(session_name)
    academic_year = year_match.group(1) if year_match else ""
    session_type = session_name.removeprefix(academic_year).strip() if academic_year else session_name

    content = f"{session_name}\nЛинк за преземање: {download_url}"

    metadata: dict[str, str] = {"filename": filename}
    if academic_year:
        metadata["academic_year"] = academic_year
    if session_type:
        metadata["session_type"] = session_type

    return session_name, content, metadata


def extract_session_file_content(filename: str, data: bytes) -> tuple[str, datetime | None]:
    """XLSX (2022+) gets the grid parser, which also gives us a date. Older PDFs only
    give plain text and no date. Anything else returns ""."""
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return extract_xlsx_schedule_grid(data)
    if lower.endswith(".pdf"):
        return extract_pdf_text(data), None
    logger.warning("Unrecognized exam-session file type, skipping content extraction: %s", filename)
    return "", None


def scrape_sessions(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        response = client.get(SESSIONS_JSON_URL)
        response.raise_for_status()
        data = response.json()

        for session_name, filename in data.items():
            url = f"{SESSIONS_BASE_URL}/{filename}"
            if skip_urls is not None and url in skip_urls:
                continue
            title, content, metadata = parse_session_entry(session_name, filename)

            # On a failed download/parse, skip the file instead of saving a worse
            # version - that would overwrite the good one we already have.
            try:
                file_response = get(client, url)
                extracted, published_at = extract_session_file_content(filename, file_response.content)
            except Exception:
                logger.exception("Failed to fetch or parse exam-session file: %s", url)
                continue

            if extracted:
                content = f"{content}\n{extracted}"

            yield NormalizedDocument(
                source="finki_hub",
                type="schedule",
                title=title,
                url=url,
                content=content,
                published_at=published_at,
                metadata=metadata,
            ).clean()
