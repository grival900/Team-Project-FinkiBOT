import logging
from collections.abc import Iterator

from backend.scrapers.finki_hub.base import STAFF_JSON_URL
from backend.scrapers.http import make_client
from backend.scrapers.normalize import NormalizedDocument

logger = logging.getLogger(__name__)


def parse_staff_entry(entry: dict) -> tuple[str, str, dict]:
    """Pure parsing step, unit-testable. Returns (name, content, metadata)."""
    name = entry.get("name", "")
    title = entry.get("title", "")
    position = entry.get("position", "")
    email = entry.get("email", "")
    cabinet = entry.get("cabinet", "")
    profile = entry.get("profile", "")
    courses_url = entry.get("courses", "")
    consultations = entry.get("consultations", "")

    lines = [name]
    if title and position:
        lines.append(f"{title}, {position}")
    elif title or position:
        lines.append(title or position)
    if email:
        lines.append(f"Е-пошта: {email}")
    if cabinet:
        lines.append(f"Кабинет: {cabinet}")
    if consultations:
        lines.append(f"Консултации: {consultations}")
    if courses_url:
        lines.append(f"Курсеви: {courses_url}")

    metadata: dict[str, str] = {}
    if email:
        metadata["email"] = email
    if title:
        metadata["title"] = title
    if position:
        metadata["position"] = position
    if cabinet:
        metadata["cabinet"] = cabinet
    if profile:
        metadata["profile"] = profile
    if courses_url:
        metadata["courses_url"] = courses_url
    if consultations:
        metadata["consultations"] = consultations

    return name, "\n".join(lines), metadata


def scrape_staff(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        response = client.get(STAFF_JSON_URL)
        response.raise_for_status()
        entries = response.json()

    for entry in entries:
        if entry.get("active") != "1":
            continue

        name, content, metadata = parse_staff_entry(entry)
        if not name:
            continue

        url = metadata.get("profile", "")
        if not url:
            url = f"https://finki.ukim.mk/staff/{name.lower().replace(' ', '-')}"
        if skip_urls is not None and url in skip_urls:
            continue

        yield NormalizedDocument(
            source="finki_hub",
            type="staff",
            title=name,
            url=url,
            content=content,
            metadata=metadata,
        ).clean()
