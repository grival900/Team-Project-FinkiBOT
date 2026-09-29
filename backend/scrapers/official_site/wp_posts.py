"""Events, projects and jobs/internships from the WordPress REST API
(/wp-json/wp/v2/<type>). The listing already has the full content, so it's one
request per 100 posts. Pages are counted with the X-WP-TotalPages header.
"""

import html
import logging
from collections.abc import Iterator
from datetime import datetime

import httpx

from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import DocumentType, NormalizedDocument
from backend.scrapers.official_site.base import BASE_URL, element_to_text, parse_html

logger = logging.getLogger(__name__)

PER_PAGE = 100
# just in case X-WP-TotalPages is ever wrong
MAX_PAGES = 50


def _html_to_text(html: str) -> str:
    return element_to_text(parse_html(html))


def parse_wp_post_row(row: dict) -> tuple[str, str, str, str | None]:
    """Pure parsing step, unit-testable against a saved fixture row. Returns
    (title, url, content_text, iso_date_text)."""
    # titles come HTML-encoded ("&#8211;"), unlike the content we parse below
    title = html.unescape(row.get("title", {}).get("rendered", ""))
    url = row.get("link", "")
    content_html = row.get("content", {}).get("rendered", "")
    content = _html_to_text(content_html)
    date_text = row.get("date")
    return title, url, content, date_text


def _iter_listing(client: httpx.Client, rest_base: str) -> Iterator[dict]:
    """Yields raw WP REST post objects across every page of `rest_base`'s listing."""
    page_num = 1
    total_pages = 1
    while page_num <= total_pages and page_num <= MAX_PAGES:
        url = f"{BASE_URL}/wp-json/wp/v2/{rest_base}?per_page={PER_PAGE}&page={page_num}"
        response = get(client, url)
        total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
        yield from response.json()
        page_num += 1


def scrape_wp_post_type(
    rest_base: str, doc_type: DocumentType, skip_urls: set[str] | None = None
) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        try:
            rows = list(_iter_listing(client, rest_base))
        except httpx.HTTPError:
            logger.exception("Failed to list WordPress post type: %s", rest_base)
            return

        for row in rows:
            title, url, content, date_text = parse_wp_post_row(row)
            if not url or not content:
                continue
            if skip_urls is not None and url in skip_urls:
                continue

            published_at = datetime.fromisoformat(date_text) if date_text else None

            yield NormalizedDocument(
                source="official",
                type=doc_type,
                title=title or url,
                url=url,
                content=content,
                published_at=published_at,
            ).clean()


def scrape_events(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    return scrape_wp_post_type("event", "event", skip_urls)


def scrape_projects(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    return scrape_wp_post_type("project", "project", skip_urls)


def scrape_jobs_and_internships(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    return scrape_wp_post_type("jobs-and-internships", "job", skip_urls)
