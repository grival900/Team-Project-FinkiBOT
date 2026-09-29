from bs4 import BeautifulSoup

PREDMETI_URL = "https://predmeti.finki-hub.com"
DIPLOMSKI_URL = "https://diplomski.finki-hub.com"
SNIMKI_URL = "https://snimki.finki-hub.com"
RASPOREDI_URL = "https://rasporedi.finki-hub.com"

ASSETS_BASE_URL = "https://assets.finki-hub.com"
COURSES_JSON_URL = f"{ASSETS_BASE_URL}/courses.json"
STAFF_JSON_URL = f"{ASSETS_BASE_URL}/staff.json"
SESSIONS_JSON_URL = f"{ASSETS_BASE_URL}/sessions.json"
SESSIONS_BASE_URL = f"{ASSETS_BASE_URL}/sessions"
OFFICIAL_SUBJECT_BASE = "https://www.finki.ukim.mk/mk/subject"


def parse_html(content: str) -> BeautifulSoup:
    return BeautifulSoup(content, "lxml")


def element_to_text(el) -> str:
    """VitePress inserts an invisible zero-width-space anchor marker ("​") next to every
    heading for deep-linking, which must be filtered out alongside blank lines."""
    text = el.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line and line != "​")
