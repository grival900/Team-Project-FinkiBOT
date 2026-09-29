"""PDFs linked from finki.ukim.mk pages - rulebooks, statutes, guides, forms, study
program elaborates.

Pages come from the WordPress REST API (/wp-json/wp/v2/pages). Most pages have their
content there; page-builder pages come back empty, so for those we fetch the HTML.
Only documents that a page links to are taken (the media library also holds election
reports, reviews and CVs we don't want). Each document remembers the page linking to it.
"""

import html as html_lib
import logging
import re
from collections.abc import Iterator
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlparse

import httpx

from backend.ingestion.file_extraction import extract_pdf_text
from backend.scrapers.http import get, make_client
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.official_site.base import BASE_URL, INFO_PAGE_CONTENT_SELECTORS, parse_html

logger = logging.getLogger(__name__)

PAGES_API = f"{BASE_URL}/wp-json/wp/v2/pages"
ALLOWED_HOSTS = ("finki.ukim.mk", "ukim.edu.mk")
# not useful for students, same pages info_pages.py leaves out
EXCLUDED_PAGES = ("finansii", "javni-nabavki", "izveshtai-za-fakultetot")
MAX_FILE_BYTES = 25_000_000
MIN_TEXT_LENGTH = 300  # less than this is a scanned PDF with no text layer
# link texts that say nothing about the file
_VAGUE_LINK_TEXT = {"овде", "тука", "линк", "преземи", "превземи", "here", "link", "download", "pdf"}


def pdf_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """(absolute url, link text) for every PDF link in a piece of HTML."""
    soup = parse_html(html)
    links = []
    for a in soup.select("a[href]"):
        url = urljoin(base_url, a["href"].strip()).split("#")[0].split("?")[0]
        if urlparse(url).scheme in ("http", "https") and url.lower().endswith(".pdf"):
            links.append((url, " ".join(a.get_text(" ").split())))
    return links


def page_content_html(page_html: str) -> str:
    """The content area of a full page, so menu and footer links are left out."""
    soup = parse_html(page_html)
    for selector in INFO_PAGE_CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el is not None:
            return str(el)
    return ""


def is_allowed(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def document_title(link_text: str, url: str) -> str:
    if len(link_text) > 3 and link_text.lower() not in _VAGUE_LINK_TEXT:
        return link_text
    # "pravilnik-iii_ciklus-31.12.2020.pdf" -> "pravilnik iii ciklus 31.12.2020"
    return re.sub(r"[-_]+", " ", PurePosixPath(unquote(urlparse(url).path)).stem).strip()


def _iter_pages(client: httpx.Client) -> Iterator[dict]:
    page = 1
    while True:
        response = get(client, f"{PAGES_API}?per_page=100&page={page}&_fields=link,title,content")
        yield from response.json()
        if page >= int(response.headers.get("X-WP-TotalPages", "1")):
            return
        page += 1


def find_linked_pdfs(client: httpx.Client) -> dict[str, dict]:
    """{pdf url: {"title", "parent_url", "parent_title"}}, first linking page wins."""
    found: dict[str, dict] = {}
    for page in _iter_pages(client):
        page_url = page["link"]
        if any(part in page_url for part in EXCLUDED_PAGES):
            continue
        html = page["content"]["rendered"]
        if not html.strip() or not parse_html(html).get_text(strip=True):
            try:
                html = page_content_html(get(client, page_url).text)
            except httpx.HTTPError:
                logger.warning("Could not fetch page %s", page_url)
                continue
        parent_title = html_lib.unescape(page["title"]["rendered"]).strip()
        for url, text in pdf_links(html, page_url):
            if is_allowed(url) and url not in found:
                found[url] = {"title": document_title(text, url), "parent_url": page_url, "parent_title": parent_title}
    return found


def build_document(url: str, info: dict, text: str) -> NormalizedDocument:
    header = f"Документ: {info['title']}\nОбјавен на страницата: {info['parent_title']}"
    return NormalizedDocument(
        source="official",
        type="document",
        title=info["title"],
        url=url,
        content=f"{header}\n{text}",
        metadata={"parent_url": info["parent_url"], "parent_title": info["parent_title"], "file_type": "pdf"},
    ).clean()


def scrape_linked_documents(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        for url, info in find_linked_pdfs(client).items():
            if skip_urls is not None and url in skip_urls:
                continue
            try:
                response = get(client, url)
            except httpx.HTTPError:
                logger.info("Dead document link %s (on %s)", url, info["parent_url"])
                continue
            data = response.content
            # dead links often redirect to an HTML "not found" page with status 200
            if not data.startswith(b"%PDF") or len(data) > MAX_FILE_BYTES:
                continue
            try:
                text = extract_pdf_text(data)
            except Exception:
                logger.warning("Could not read PDF %s", url)
                continue
            if len(text.strip()) < MIN_TEXT_LENGTH:
                continue
            yield build_document(url, info, text)
