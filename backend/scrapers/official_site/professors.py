"""Scrapes staff profiles (finki.ukim.mk/kadar/<slug>): name, email, bio and the
other tabs (books, papers, projects...).

Profiles are listed on /kadar/ (the sitemap redirects to a dead domain). All tabs are
in the HTML already, so one GET per profile is enough.
"""

import logging
from collections.abc import Iterator

import httpx

from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.official_site.base import BASE_URL, element_to_text, parse_html

logger = logging.getLogger(__name__)

LISTING_PATH = "/kadar/"
MIN_CONTENT_LENGTH = 100


def parse_listing_html(html: bytes | str) -> list[str]:
    """Pure parsing step, unit-testable. Returns absolute profile URLs from the staff directory."""
    soup = parse_html(html)
    urls: list[str] = []
    seen: set[str] = set()
    for a in soup.select("a.kadar-item__link[href]"):
        url = a["href"]
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def parse_professor_html(html: bytes | str) -> tuple[str, str, str | None]:
    """Pure parsing step, unit-testable against a saved fixture. Returns (name, content_text, email)."""
    soup = parse_html(html)
    content_el = soup.select_one(".staff-single__content")
    if content_el is None:
        return "", "", None
    name_el = content_el.select_one(".staff-name") or soup.select_one("h1")
    name = name_el.get_text(strip=True) if name_el else ""
    email_el = soup.select_one(".staff-profile__email")
    email = email_el.get_text(strip=True) if email_el else None
    return name, element_to_text(content_el), email


def scrape_professors(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        listing_response = get(client, f"{BASE_URL}{LISTING_PATH}")
        urls = parse_listing_html(listing_response.content)

        for url in urls:
            if skip_urls is not None and url in skip_urls:
                continue
            try:
                response = get(client, url)
            except httpx.HTTPError:
                logger.exception("Failed to fetch professor page: %s", url)
                continue

            if response.url.path.rstrip("/") == "/not-found":
                continue

            name, content, email = parse_professor_html(response.content)
            # admin staff often have no bio but a useful email, so keep those
            if len(content) < MIN_CONTENT_LENGTH and not email:
                continue

            yield NormalizedDocument(
                source="official",
                type="professor",
                title=name or url,
                url=url,
                content=content,
                metadata={"email": email} if email else {},
            ).clean()
