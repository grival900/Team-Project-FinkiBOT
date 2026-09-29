"""TODO: class schedules from rasporedi.finki-hub.com - not implemented yet."""

from collections.abc import Iterator

from backend.scrapers.normalize import NormalizedDocument


def scrape_schedules(skip_urls: set[str] | None = None) -> Iterator[NormalizedDocument]:
    raise NotImplementedError("schedules scraper not yet implemented — see module docstring")
    yield  # pragma: no cover
