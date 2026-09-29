"""Scrapes static pages from finki.ukim.mk: About Us, Studies, Admissions,
International Students and Contact.

The site's sitemap is broken, so PAGE_URLS is a hand-made list from the nav menu -
new pages have to be added by hand. Left out on purpose: legal/finance pages, the
English versions (many just redirect back), PDFs and pages that are only link lists.
"""

import logging
from collections.abc import Iterator

import httpx

from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.official_site.base import BASE_URL, extract_info_page_text, parse_html

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 80

PAGE_URLS = [
    # About Us
    "/za-nas/nastavno-nauchna-dejnost/za-fakultetot/",
    "/za-nas/rakovodstvo-i-organizacija/dekanat/",
    "/za-nas/rakovodstvo-i-organizacija/dekanatska-uprava/",
    "/za-nas/rakovodstvo-i-organizacija/nastavno-nauchen-sovet/",
    "/za-nas/rakovodstvo-i-organizacija/instituti-i-centri/",
    "/za-nas/rakovodstvo-i-organizacija/laboratorii/",
    "/za-nas/administracija-i-dokumenti/partnerstva/",
    "/za-nas/nastavno-nauchna-dejnost/finki-e-moj-izbor/",
    # Studies
    "/studii-2/vidovi-studii/",
    "/studii-2/vidovi-studii/dodiplomski-studii/",
    "/studii-2/vidovi-studii/magisterski-studii-2/",
    "/studii-2/vidovi-studii/doktorski-studii/",
    "/studii-2/poddrshka/studentska-sluzhba/",
    "/studii-2/poddrshka/dokumenti-i-proceduri/",
    "/studii-2/poddrshka/obrasci/",
    "/studii-2/poddrshka/erazmus/",
    "/studii-2/akademski-resursi-i-raspored/raspored-na-ispiti/",
    "/studii-2/akademski-resursi-i-raspored/akademski-kalendar/",
    "/studii-2/akademski-resursi-i-raspored/reshenija/",
    "/studii-2/zavrshni-obvrski-i-odbrani/odbrani/",
    # Admissions — undergraduate
    "/upisi/dodiplomski-studii/kvoti/",
    "/upisi/dodiplomski-studii/potrebni-dokumenti/",
    "/upisi/dodiplomski-studii/izbor-na-studiska-programa/",
    "/upisi/dodiplomski-studii/potrebni-predmeti/",
    "/upisi/dodiplomski-studii/presmetuvanje-na-bodovi/",
    "/upisi/dodiplomski-studii/stipendii/",
    # Admissions — master's
    "/upisi/magisterski-studii/kvoti/",
    "/upisi/magisterski-studii/potrebni-dokumenti/",
    "/upisi/magisterski-studii/uslovi/",
    # Admissions — PhD
    "/upisi/doktorski-studii/kvoti/",
    "/upisi/doktorski-studii/potrebni-dokumenti/",
    "/upisi/doktorski-studii/uslovi/",
    "/upisi/doktorski-studii/akreditirani-mentori/",
    # International Students
    "/internacionalni-studenti/admissions/undergraduate-studies-for-international-students/",
    "/internacionalni-studenti/admissions/masters-studies-for-international-students/",
    # Contact
    "/kontakt/",
]


def parse_info_page_html(html: bytes | str) -> tuple[str, str]:
    """Pure parsing step, unit-testable against a saved fixture. Returns (title, content_text)."""
    soup = parse_html(html)
    h1 = soup.select_one("h1")
    title = h1.get_text(strip=True) if h1 else ""
    return title, extract_info_page_text(soup)


def scrape_info_pages(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        for path in PAGE_URLS:
            url = f"{BASE_URL}{path}"
            if skip_urls is not None and url in skip_urls:
                continue
            try:
                response = get(client, url)
            except httpx.HTTPError:
                logger.exception("Failed to fetch info page: %s", url)
                continue

            title, content = parse_info_page_html(response.content)
            if len(content) < MIN_CONTENT_LENGTH:
                logger.warning("Skipping near-empty info page (%d chars): %s", len(content), url)
                continue

            yield NormalizedDocument(
                source="official",
                type="page",
                title=title or url,
                url=url,
                content=content,
            ).clean()
