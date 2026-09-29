import logging
from collections.abc import Iterator
from urllib.parse import quote

from backend.scrapers.finki_hub.base import (
    COURSES_JSON_URL,
    OFFICIAL_SUBJECT_BASE,
    PREDMETI_URL,
)
from backend.scrapers.http import make_client
from backend.scrapers.normalize import NormalizedDocument

logger = logging.getLogger(__name__)

ACCREDITATION_YEARS = ["2023", "2018"]

_FIELD_MAP = {
    "code": "Код",
    "level": "Ниво",
    "semester": "Семестар",
    "channel": "Канал",
    "name": "Име",
    "prerequisite": "Предуслов",
    "credits": "Кредити",
}

_PROGRAM_CODES = {
    "kn": "КНИ",
    "siis": "СИИС",
    "pit": "ПИТ",
    "imb": "ИМБ",
    "ki": "КИ",
    "ie": "ИЕ",
    "ke": "КЕ",
    "ssp": "ССП",
    "seis": "СЕИС",
}


def _split_names(text: str | None) -> list[str]:
    if not text:
        return []
    return [n.strip() for n in text.split("\n") if n.strip()]


def _split_tags(text: str | None) -> list[str]:
    if not text:
        return []
    return [t.strip() for t in text.split(",") if t.strip()]


def _build_accreditation(entry: dict, year: str) -> dict | None:
    if entry.get(f"{year}-available") != "TRUE":
        return None
    code = entry.get(f"{year}-code", "")
    official_url = f"{OFFICIAL_SUBJECT_BASE}/{code}" if code else None
    acc: dict[str, str | None] = {"year": year, "official_url": official_url}
    for json_suffix, mk_key in _FIELD_MAP.items():
        val = entry.get(f"{year}-{json_suffix}", "")
        if val:
            acc[mk_key] = val
    programs: dict[str, str] = {}
    for code_key, label in _PROGRAM_CODES.items():
        status = entry.get(f"{year}-state-{code_key}", "")
        if status and status != "нема":
            programs[label] = status
    if programs:
        acc["programs"] = programs
    return acc


def parse_course_entry(entry: dict) -> tuple[str, list[str], dict]:
    """Pure parsing step, unit-testable against inline JSON dicts."""
    name = entry.get("name", "")
    professors = _split_names(entry.get("professors"))
    assistants = _split_names(entry.get("assistants"))
    tags = _split_tags(entry.get("tags"))
    accreditations = []
    for year in ACCREDITATION_YEARS:
        acc = _build_accreditation(entry, year)
        if acc:
            accreditations.append(acc)
    return name, tags, {
        "professors": professors,
        "assistants": assistants,
        "accreditations": accreditations,
    }


def _format_content(name: str, tags: list[str], details: dict) -> str:
    lines = [name]
    accreditations = details["accreditations"]
    latest = accreditations[0] if accreditations else {}

    if latest.get("Код"):
        lines.append(f"Код: {latest['Код']}")
    if latest.get("Ниво") or latest.get("Семестар"):
        lines.append(f"Ниво: {latest.get('Ниво', '?')}, Семестар: {latest.get('Семестар', '?')}")
    if latest.get("Кредити"):
        lines.append(f"Кредити: {latest['Кредити']}")
    if latest.get("Предуслов"):
        lines.append(f"Предуслов: {latest['Предуслов']}")
    if details["professors"]:
        lines.append(f"Професори: {', '.join(details['professors'])}")
    if details["assistants"]:
        lines.append(f"Асистенти: {', '.join(details['assistants'])}")
    if tags:
        lines.append(f"Тагови: {', '.join(tags)}")

    programs = latest.get("programs", {})
    if programs:
        mandatory = [p for p, s in programs.items() if s == "задолжителен"]
        elective = [p for p, s in programs.items() if s.startswith("изборен")]
        if mandatory:
            lines.append(f"Задолжителен за: {', '.join(mandatory)}")
        if elective:
            lines.append(f"Изборен за: {', '.join(elective)}")

    years = ", ".join(a["year"] for a in accreditations if a["year"])
    if years:
        lines.append(f"Акредитации: {years}")

    return "\n".join(lines)


def scrape_courses(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    with make_client() as client:
        response = client.get(COURSES_JSON_URL)
        response.raise_for_status()
        entries = response.json()

    for entry in entries:
        name, tags, details = parse_course_entry(entry)
        if not name:
            continue

        accreditations = details["accreditations"]
        official_url = next(
            (a["official_url"] for a in accreditations if a.get("official_url")),
            None,
        )

        metadata = {
            "accreditation_years": [a["year"] for a in accreditations if a["year"]],
            "tags": tags,
            "professors": details["professors"],
            "assistants": details["assistants"],
            "accreditations": accreditations,
        }
        if official_url:
            metadata["official_subject_url"] = official_url

        url = f"{PREDMETI_URL}/?course={quote(name)}"
        if skip_urls is not None and url in skip_urls:
            continue

        yield NormalizedDocument(
            source="finki_hub",
            type="course",
            title=name,
            url=url,
            content=_format_content(name, tags, details),
            metadata=metadata,
        ).clean()
