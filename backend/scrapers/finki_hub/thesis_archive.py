"""Bachelor and master theses from the JSON APIs behind diplomski.finki-hub.com:

    https://diplomski-api.finki-hub.com/diplomas   (~4000 bachelor theses)
    https://magisterski-api.finki-hub.com/masters  (~60 master theses)

One request each. We keep the title, abstract, mentor, committee, status and date.
Student names are dropped on purpose - only the index number is kept.
"""

import hashlib
import logging
from collections.abc import Iterator
from datetime import datetime

from backend.scrapers.http import make_client
from backend.scrapers.normalize import NormalizedDocument

logger = logging.getLogger(__name__)

DIPLOMAS_URL = "https://diplomski-api.finki-hub.com/diplomas"
MASTERS_URL = "https://magisterski-api.finki-hub.com/masters"
DIPLOMAS_PAGE = "https://diplomski.finki-hub.com/"
MASTERS_PAGE = "https://diplomski.finki-hub.com/masters"


def student_index(student: str) -> str:
    """ "221096 - Анастасија Корабоска" -> "221096" (the name is not kept)."""
    return student.split(" - ")[0].strip()


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y")
    except ValueError:
        return None


def parse_thesis(row: dict, level: str) -> NormalizedDocument:
    """`level` is "bachelor" or "master" - the two APIs name a few fields differently."""
    is_master = level == "master"
    index = student_index(row.get("student", ""))
    title = row.get("title", "").strip()
    committee = [row.get("president", ""), row.get("member", "")] if is_master else [row.get("member1", ""), row.get("member2", "")]
    committee = [c for c in committee if c]
    date = row.get("dateOfPresentation" if is_master else "dateOfSubmission", "")
    file_id = row.get("fileId")
    api = MASTERS_URL if is_master else DIPLOMAS_URL
    pdf_url = f"{api}/download/{file_id}" if file_id else None

    kind = "Магистерска работа" if is_master else "Дипломска работа"
    lines = [
        f"{kind}: {title}",
        f"Индекс на студентот: {index}",
        f"Ментор: {row.get('mentor', '')}",
        f"Комисија: {', '.join(committee)}" if committee else "",
        f"Статус: {row.get('status', '')}",
        f"{'Датум на одбрана' if is_master else 'Датум на пријава'}: {date}" if date else "",
        f"Опис: {row.get('description', '').strip()}",
    ]

    # The page has no link per thesis, so the URL just has to be stable and unique.
    # It doesn't use fileId, because a thesis only gets a file later on.
    key = hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
    page = MASTERS_PAGE if is_master else DIPLOMAS_PAGE
    metadata = {
        "level": level,
        "student_index": index,
        "mentor": row.get("mentor", ""),
        "committee": committee,
        "status": row.get("status", ""),
        "date": date,
    }
    if pdf_url:
        metadata["pdf_url"] = pdf_url

    return NormalizedDocument(
        source="finki_hub",
        type="thesis",
        title=title,
        url=f"{page}?thesis={index}-{key}",
        content="\n".join(line for line in lines if line),
        published_at=_parse_date(date),
        metadata=metadata,
    ).clean()


def scrape_thesis_archive(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    seen: set[str] = set()
    with make_client() as client:
        for url, level in ((DIPLOMAS_URL, "bachelor"), (MASTERS_URL, "master")):
            response = client.get(url, timeout=120.0)  # the bachelor list is ~6MB
            response.raise_for_status()
            for row in response.json():
                if not row.get("title"):
                    continue
                doc = parse_thesis(row, level)
                # a student can register the same title twice
                if doc.url in seen:
                    continue
                seen.add(doc.url)
                if skip_urls is not None and doc.url in skip_urls:
                    continue
                yield doc
