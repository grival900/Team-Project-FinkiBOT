"""`_run_ingestion_locked` in incremental mode hands each scraper the set of URLs
already indexed for its source; a full run passes `skip_urls=None`."""

from unittest.mock import MagicMock, patch

from backend.ingestion import pipeline
from backend.scrapers.registry import ScraperEntry


def _run(incremental, known=None):
    session_ctx = MagicMock()
    session_ctx.__enter__.return_value = MagicMock()

    fn = MagicMock(return_value=iter([]))
    entry = ScraperEntry(name="fake.scraper", source="official", fn=fn, cadence="frequent")

    with (
        patch.object(pipeline, "SessionLocal", return_value=session_ctx),
        patch.object(pipeline, "SCRAPERS", [entry]),
        patch.object(pipeline, "get_bool_setting", return_value=True),
        patch.object(pipeline, "_known_urls_by_source", return_value=known or {}),
    ):
        pipeline._run_ingestion_locked(None, incremental=incremental)

    return fn


def test_full_run_passes_no_skip_set():
    _run(incremental=False).assert_called_once_with(skip_urls=None)


def test_incremental_run_hands_the_scraper_its_sources_known_urls():
    known = {"official": {"https://x/1", "https://x/2"}, "finki_hub": {"https://y/1"}}
    _run(incremental=True, known=known).assert_called_once_with(skip_urls={"https://x/1", "https://x/2"})


def test_incremental_run_passes_an_empty_set_when_the_source_has_nothing_indexed():
    _run(incremental=True, known={"finki_hub": {"https://y/1"}}).assert_called_once_with(skip_urls=set())
