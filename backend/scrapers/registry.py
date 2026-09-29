"""All scrapers the ingestion pipeline can run. Unfinished ones are `enabled=False`."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal

from backend.scrapers.finki_hub.consultations import scrape_consultations
from backend.scrapers.finki_hub.courses import scrape_courses
from backend.scrapers.finki_hub.recordings import scrape_recordings
from backend.scrapers.finki_hub.schedules import scrape_schedules
from backend.scrapers.finki_hub.sessions import scrape_sessions
from backend.scrapers.finki_hub.staff import scrape_staff
from backend.scrapers.finki_hub.thesis_archive import scrape_thesis_archive
from backend.scrapers.normalize import NormalizedDocument
from backend.scrapers.official_site.announcements import scrape_announcements
from backend.scrapers.official_site.info_pages import scrape_info_pages
from backend.scrapers.official_site.linked_documents import scrape_linked_documents
from backend.scrapers.official_site.professors import scrape_professors
from backend.scrapers.official_site.schedule_links import scrape_schedule_links
from backend.scrapers.official_site.subjects import scrape_subjects
from backend.scrapers.official_site.wp_posts import scrape_events, scrape_jobs_and_internships, scrape_projects


Cadence = Literal["frequent", "slow"]


@dataclass
class ScraperEntry:
    name: str
    source: str
    # called as fn(skip_urls=...) - URLs to skip on an incremental run, else None
    fn: Callable[..., Iterator[NormalizedDocument]]
    enabled: bool = True
    # "frequent" = few requests, runs hourly. "slow" = one request per page, runs weekly.
    cadence: Cadence = "frequent"


SCRAPERS: list[ScraperEntry] = [
    ScraperEntry(name="official.announcements", source="official", fn=scrape_announcements, cadence="frequent"),
    ScraperEntry(name="official.schedule_links", source="official", fn=scrape_schedule_links, cadence="frequent"),
    ScraperEntry(name="official.professors", source="official", fn=scrape_professors, cadence="slow"),
    # static pages - few of them, but they rarely change
    ScraperEntry(name="official.info_pages", source="official", fn=scrape_info_pages, cadence="slow"),
    # PDFs linked from the pages (rulebooks, guides...); downloads ~100 files
    ScraperEntry(
        name="official.linked_documents", source="official", fn=scrape_linked_documents, cadence="slow"
    ),
    # WordPress REST listings already include the full content, so these are cheap
    ScraperEntry(name="official.events", source="official", fn=scrape_events, cadence="frequent"),
    ScraperEntry(name="official.projects", source="official", fn=scrape_projects, cadence="frequent"),
    ScraperEntry(
        name="official.jobs_and_internships", source="official", fn=scrape_jobs_and_internships, cadence="frequent"
    ),
    # official.subjects must run after finki_hub.courses - it uses the URLs it found
    ScraperEntry(name="finki_hub.courses", source="finki_hub", fn=scrape_courses, cadence="frequent"),
    ScraperEntry(name="official.subjects", source="official", fn=scrape_subjects, cadence="slow"),
    ScraperEntry(name="finki_hub.recordings", source="finki_hub", fn=scrape_recordings, cadence="slow"),
    ScraperEntry(name="finki_hub.staff", source="finki_hub", fn=scrape_staff, cadence="frequent"),
    # one request per staff member (~96)
    ScraperEntry(name="finki_hub.consultations", source="finki_hub", fn=scrape_consultations, cadence="slow"),
    # downloads and parses ~40 spreadsheets, which don't change once published
    ScraperEntry(name="finki_hub.sessions", source="finki_hub", fn=scrape_sessions, cadence="slow"),
    ScraperEntry(
        name="finki_hub.thesis_archive", source="finki_hub", fn=scrape_thesis_archive, cadence="frequent"
    ),
    ScraperEntry(
        name="finki_hub.schedules", source="finki_hub", fn=scrape_schedules, enabled=False, cadence="frequent"
    ),
]
