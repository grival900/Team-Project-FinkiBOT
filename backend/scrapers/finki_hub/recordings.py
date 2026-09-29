"""Scrapes snimki.finki-hub.com - student-maintained lecture recordings and notes,
one page per course (linked from the /introduction.html sidebar).

Saved as markdown so the recording links and headings survive and can be shown
as clickable links on our document page.
"""

import logging
from collections.abc import Iterator
from urllib.parse import urljoin

import httpx
from bs4 import Tag

from backend.scrapers.finki_hub.base import SNIMKI_URL, parse_html
from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument

logger = logging.getLogger(__name__)

INTRODUCTION_PATH = "/introduction.html"


def parse_course_links(html: bytes | str) -> list[str]:
    """Pure parsing step, unit-testable against a saved fixture. Returns absolute course-page URLs."""
    soup = parse_html(html)
    urls = {urljoin(SNIMKI_URL, a["href"]) for a in soup.select('a[href*="/courses/"]')}
    return sorted(urls)


def _to_markdown(root: Tag) -> str:
    lines: list[str] = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "li", "p"]):
        if el.name in ("h1", "h2", "h3", "h4"):
            anchor = el.select_one(".header-anchor")
            if anchor is not None:
                anchor.decompose()  # VitePress's zero-width-space deep-link marker
            text = el.get_text(strip=True)
            if not text:
                continue
            # keep the h1 - only content gets embedded, so the course name must be in it
            lines.append(f"{'#' * int(el.name[1])} {text}")
            continue

        link = el.find("a", href=True)
        if link is not None:
            label = link.get_text(strip=True)
            if label:
                lines.append(f"- [{label}]({link['href']})")
            continue

        text = el.get_text(strip=True)
        if text:
            lines.append(f"- {text}" if el.name == "li" else text)
    return "\n".join(lines)


def parse_course_page_html(html: bytes | str) -> tuple[str, str]:
    """Pure parsing step. Returns (title, content_markdown)."""
    soup = parse_html(html)
    main_el = soup.select_one(".vp-doc")
    if main_el is None:
        return "", ""
    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True).replace("​", "") if title_el else ""
    return title, _to_markdown(main_el)


def scrape_recordings(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        intro_response = get(client, f"{SNIMKI_URL}{INTRODUCTION_PATH}")
        urls = parse_course_links(intro_response.content)

        for url in urls:
            if skip_urls is not None and url in skip_urls:
                continue
            try:
                response = get(client, url)
            except httpx.HTTPError:
                logger.exception("Failed to fetch recordings page: %s", url)
                continue

            title, content = parse_course_page_html(response.content)
            if not content:
                continue

            yield NormalizedDocument(
                source="finki_hub",
                type="material",
                title=title or url,
                url=url,
                content=content,
            ).clean()
