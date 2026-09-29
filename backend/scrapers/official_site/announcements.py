"""Scrapes the announcement board through the WordPress REST API
(/wp-json/wp/v2/announcement). The listing already contains each post's full text,
so it's one request per 100 announcements.

Pages are fetched lazily so we can stop early (limit reached, or only known posts left).
"""

import logging
from collections.abc import Iterator
from datetime import datetime

import httpx

from backend.core.config import get_settings
from backend.core.site_settings import get_setting_cached, parse_int_or_none
from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.official_site.base import BASE_URL
from backend.scrapers.official_site.wp_posts import parse_wp_post_row

logger = logging.getLogger(__name__)

REST_BASE = "announcement"
PER_PAGE = 100
MAX_PAGES = 200  # safety cap; ~1008 announcements today, comfortably under 200*100
# Newest first, so after this many known posts in a row we assume the rest are old too.
# Not 1, in case a post was back-dated.
INCREMENTAL_STOP_AFTER_KNOWN = 10


def _iter_rows(client: httpx.Client) -> Iterator[dict]:
    """Yields raw WP REST announcement objects, newest first, across every listing
    page — lazily, so a caller that stops early never fetches the remaining pages."""
    page_num = 1
    total_pages = 1
    while page_num <= total_pages and page_num <= MAX_PAGES:
        url = f"{BASE_URL}/wp-json/wp/v2/{REST_BASE}?per_page={PER_PAGE}&page={page_num}"
        try:
            response = get(client, url)
        except httpx.HTTPError:
            logger.exception("Failed to fetch announcement listing page %d", page_num)
            return
        total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
        yield from response.json()
        page_num += 1


def scrape_announcements(
    skip_urls: set[str] | None = None,
) -> Iterator[NormalizedDocument]:
    """Scrape announcements from the WordPress REST API.

    The API is newest-first and paginated. If scrape_announcement_limit is set,
    only that many new announcements are yielded.

    During incremental runs, already-indexed URLs are skipped. Once enough
    consecutive known announcements are encountered, we stop because older
    pages are unlikely to contain new content.
    """
    limit = get_setting_cached(
        "scrape_announcement_limit",
        get_settings().scrape_announcement_limit,
        parse_int_or_none,
    )

    yielded = 0
    consecutive_known = 0

    with make_client() as client:
        for row in _iter_rows(client):
            # Respect configured scrape limit.
            if limit is not None and yielded >= limit:
                break

            title, url, content, date_text = parse_wp_post_row(row)

            if not url:
                continue

            # Incremental mode: skip announcements already indexed.
            if skip_urls is not None and url in skip_urls:
                consecutive_known += 1

                if consecutive_known >= INCREMENTAL_STOP_AFTER_KNOWN:
                    break

                continue

            # We found something new, so reset the consecutive-known counter.
            consecutive_known = 0

            published_at = (
                datetime.fromisoformat(date_text)
                if date_text
                else None
            )

            yield NormalizedDocument(
                source="official",
                type="announcement",
                title=title or url,
                url=url,
                content=content or title,
                published_at=published_at,
            ).clean()

            yielded += 1