"""Scrapes each professor's consultation slots from consultations.finki.ukim.mk.

The page URLs come from staff.json. It's one request per professor (~96), so this is
a separate "slow" scraper instead of part of scrape_staff. Each page has either
"Нема закажани консултации..." or one .consultation-card per slot.
"""

import logging
from collections.abc import Iterator

import httpx

from backend.scrapers.finki_hub.base import STAFF_JSON_URL, parse_html
from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument

logger = logging.getLogger(__name__)

NO_SLOTS_SELECTOR = "h5.text-muted"
_RELEVANT_FIELDS = {"Датум", "Време", "Локација"}


def parse_consultations_html(html: bytes | str) -> str:
    """One line per slot (date, time and room together), or the "none scheduled" message."""
    soup = parse_html(html)

    empty_el = soup.select_one(NO_SLOTS_SELECTOR)
    if empty_el is not None:
        return empty_el.get_text(strip=True)

    lines: list[str] = []
    for card in soup.select(".consultation-card"):
        fields: dict[str, str] = {}
        for item in card.select(".info-item"):
            label_el = item.find("strong")
            if label_el is None:
                continue
            label = label_el.get_text(strip=True)
            if label not in _RELEVANT_FIELDS:
                continue
            value_el = label_el.find_next_sibling("span")
            fields[label] = value_el.get_text(strip=True) if value_el else ""

        if fields:
            lines.append(", ".join(f"{label}: {value}" for label, value in fields.items()))

    return "\n".join(lines)


def scrape_consultations(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        response = client.get(STAFF_JSON_URL)
        response.raise_for_status()
        entries = response.json()

        for entry in entries:
            if entry.get("active") != "1":
                continue
            name = entry.get("name", "")
            url = entry.get("consultations", "")
            if not name or not url:
                continue
            if skip_urls is not None and url in skip_urls:
                continue

            try:
                page = get(client, url)
            except httpx.HTTPError:
                logger.exception("Failed to fetch consultations page: %s", url)
                continue

            content = parse_consultations_html(page.content)
            if not content:
                continue

            yield NormalizedDocument(
                source="finki_hub",
                type="consultation",
                title=name,
                url=url,
                content=f"{name}\n{content}",
            ).clean()
