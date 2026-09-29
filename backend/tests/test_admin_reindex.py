from unittest.mock import patch

import pytest

from backend.api.routers import admin
from backend.ingestion.pipeline import ScraperStats

STATS = {"official.announcements": ScraperStats(seen=5, new=2, updated=1, unchanged=2)}


@pytest.fixture(autouse=True)
def _reset_job():
    admin._reindex_job = None
    yield
    admin._reindex_job = None


def _run(
    cadence=None,
    refresh_seed=True,
    incremental=False,
    ingestion=None,
    ingestion_exc=None,
    seed_exc=None,
):
    """Invoke the background worker directly (the endpoint just spawns it in a thread)
    with run_ingestion / export_seed stubbed. Returns (run_ingestion_mock, export_seed_mock)."""
    ing_kw = {"side_effect": ingestion_exc} if ingestion_exc else {"return_value": ingestion or {}}
    seed_kw = {"side_effect": seed_exc} if seed_exc else {"return_value": 123}
    with (
        patch.object(admin, "run_ingestion", **ing_kw) as run_ingestion,
        patch.object(admin, "export_seed", **seed_kw) as export_seed,
    ):
        admin._background_reindex(cadence, refresh_seed, incremental)
    return run_ingestion, export_seed


def test_reindex_refreshes_the_seed_after_a_successful_run():
    _, export_seed = _run(ingestion=STATS)

    export_seed.assert_called_once_with()
    job = admin._reindex_job
    assert job.state == "done"
    assert job.seed_refreshed is True
    assert job.seed_document_count == 123


def test_reindex_records_the_per_scraper_diff():
    _run(ingestion=STATS)

    (row,) = admin._reindex_job.scrapers
    assert (row.name, row.seen, row.new, row.updated, row.unchanged) == (
        "official.announcements",
        5,
        2,
        1,
        2,
    )


def test_reindex_passes_cadence_and_a_progress_callback_through():
    run_ingestion, _ = _run(cadence="frequent", ingestion=STATS)

    args, kwargs = run_ingestion.call_args
    assert args[0] == "frequent"
    assert callable(kwargs["progress_cb"])
    assert kwargs["incremental"] is False


def test_reindex_threads_the_incremental_flag_through_and_records_it():
    run_ingestion, _ = _run(incremental=True, ingestion=STATS)

    assert run_ingestion.call_args.kwargs["incremental"] is True
    assert admin._reindex_job.incremental is True
    assert admin.reindex_status().incremental is True


def test_progress_callback_updates_the_job():
    """The callback pipeline.run_ingestion invokes must move the job's progress fields."""
    captured = {}

    def fake_run_ingestion(cadence, progress_cb=None, incremental=False, name=None):
        progress_cb(0, 2, "official.announcements")
        progress_cb(1, 2, "finki_hub.courses")
        captured["mid"] = (admin._reindex_job.progress_done, admin._reindex_job.current_scraper)
        progress_cb(2, 2, None)
        return STATS

    with (
        patch.object(admin, "run_ingestion", side_effect=fake_run_ingestion),
        patch.object(admin, "export_seed", return_value=1),
    ):
        admin._background_reindex(None, refresh_seed=False)

    assert captured["mid"] == (1, "finki_hub.courses")
    assert admin._reindex_job.progress_done == 2
    assert admin._reindex_job.progress_total == 2
    assert admin._reindex_job.current_scraper is None


def test_reindex_does_not_refresh_seed_when_refresh_seed_is_false():
    _, export_seed = _run(refresh_seed=False, ingestion=STATS)

    export_seed.assert_not_called()
    assert admin._reindex_job.state == "done"
    assert admin._reindex_job.seed_refreshed is False


def test_reindex_marks_error_when_another_run_holds_the_lock():
    """run_ingestion returns {} when another ingestion is already running."""
    _, export_seed = _run(ingestion={})

    export_seed.assert_not_called()
    assert admin._reindex_job.state == "error"
    assert "already in progress" in admin._reindex_job.error


def test_reindex_swallows_a_seed_export_failure():
    _, export_seed = _run(ingestion=STATS, seed_exc=OSError("read-only fs"))

    export_seed.assert_called_once_with()
    job = admin._reindex_job
    assert job.state == "done"  # the run itself succeeded
    assert job.seed_refreshed is False


def test_reindex_ingestion_failure_is_recorded_and_skips_the_seed():
    _, export_seed = _run(ingestion_exc=RuntimeError("scraper blew up"))

    export_seed.assert_not_called()
    job = admin._reindex_job
    assert job.state == "error"
    assert job.error == "scraper blew up"


def test_status_is_idle_before_any_run():
    assert admin.reindex_status().state == "idle"


def test_status_reports_duration_and_diff_after_a_run():
    _run(ingestion=STATS)

    out = admin.reindex_status()
    assert out.state == "done"
    assert out.duration_seconds is not None and out.duration_seconds >= 0
    assert out.seed_document_count == 123
    assert [s.name for s in out.scrapers] == ["official.announcements"]
