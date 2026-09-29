"""Scrapes the "Распоред на часови и консултации" links on /announcements/ - links to
the current exam-session spreadsheets, the campus map, etc.

Only the title and link are saved, not the spreadsheet itself, so the bot can at
least point students to the right file.

    section.schedule-section > a.schedule-card[href]
        span.schedule-card__heading   -> title
        span.schedule-card__subtitle  -> optional subtitle
"""

from collections.abc import Iterator

from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.official_site.base import BASE_URL, parse_html

# this widget isn't in the REST API, so we still need the HTML page
LISTING_PATH = "/announcements/"


def parse_schedule_links_html(html: bytes | str) -> list[tuple[str, str]]:
    """Pure parsing step, unit-testable against a saved fixture. Returns (title, url) pairs."""
    soup = parse_html(html)
    section = soup.select_one(".schedule-section")
    if section is None:
        return []

    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    for card in section.select("a.schedule-card[href]"):
        href = card["href"].strip()
        heading_el = card.select_one(".schedule-card__heading")
        subtitle_el = card.select_one(".schedule-card__subtitle")
        heading = heading_el.get_text(strip=True) if heading_el else ""
        subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ""
        text = f"{heading} {subtitle}".strip()
        if not href or not text or href in seen:
            continue
        seen.add(href)
        results.append((text, href))

    return results


def scrape_schedule_links(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        response = get(client, f"{BASE_URL}{LISTING_PATH}")

    for title, url in parse_schedule_links_html(response.content):
        if skip_urls is not None and url in skip_urls:
            continue
        yield NormalizedDocument(
            source="official",
            type="schedule",
            title=title,
            url=url,
            content=title,
        ).clean()
