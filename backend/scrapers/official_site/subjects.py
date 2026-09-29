"""Scrapes official syllabus pages (finki.ukim.mk/mk/subject/<code>) for what
finki-hub doesn't have: learning objectives, content and literature.

There's no list of these pages, so the URLs come from the `official_subject_url` of
already-indexed finki-hub courses (finki_hub.courses has to run first). It's ~180
pages at 1 request/second, so SCRAPE_SUBJECTS_LIMIT caps how many per run.
"""

import logging
from collections.abc import Iterator

import httpx

from backend.core.config import get_settings
from backend.core.site_settings import get_setting_cached, parse_int_or_none
from backend.db import SessionLocal
from backend.models import Document
from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.official_site.base import element_to_text, parse_html

logger = logging.getLogger(__name__)


def _subject_urls_from_courses() -> list[str]:
    with SessionLocal() as db:
        rows = db.query(Document.doc_metadata).filter(Document.source == "finki_hub", Document.type == "course")
        urls = sorted({url for (metadata,) in rows if (url := metadata.get("official_subject_url"))})

    limit = get_setting_cached("scrape_subjects_limit", get_settings().scrape_subjects_limit, parse_int_or_none)
    return urls[:limit] if limit is not None else urls


def parse_subject_html(html: bytes | str) -> tuple[str, str]:
    """Pure parsing step, unit-testable against a saved fixture. Returns (title, content_text)."""
    soup = parse_html(html)
    body_el = soup.select_one(".region-content")
    if body_el is None:
        return "", ""
    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""
    return title, element_to_text(body_el)


def scrape_subjects(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    urls = _subject_urls_from_courses()

    with make_client() as client:
        for url in urls:
            if skip_urls is not None and url in skip_urls:
                continue
            try:
                response = get(client, url)
            except httpx.HTTPError:
                logger.exception("Failed to fetch subject page: %s", url)
                continue

            title, content = parse_subject_html(response.content)
            if not content:
                continue

            yield NormalizedDocument(
                source="official",
                type="course",
                title=title or url,
                url=url,
                content=content,
            ).clean()
