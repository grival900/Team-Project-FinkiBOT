import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.scrapers.official_site import announcements
from backend.scrapers.official_site.announcements import scrape_announcements

FIXTURES = Path(__file__).parent / "fixtures"


def _load_rows() -> list[dict]:
    return json.loads((FIXTURES / "wp_announcement_response.json").read_text(encoding="utf-8"))


def _row(slug: str, date: str | None = "2026-01-01T00:00:00") -> dict:
    return {
        "link": f"https://finki.ukim.mk/announcements/{slug}/",
        "title": {"rendered": slug},
        "content": {"rendered": f"<p>body {slug}</p>"},
        "date": date,
    }


def _paged_response(rows: list[dict]) -> MagicMock:
    return MagicMock(headers={"X-WP-TotalPages": "1"}, json=MagicMock(return_value=rows))


def test_scrape_announcements_parses_a_real_fixture_row():
    rows = _load_rows()
    with (
        patch.object(announcements, "make_client"),
        patch.object(announcements, "get", return_value=_paged_response(rows)),
        patch.object(announcements, "get_setting_cached", return_value=None),
    ):
        docs = list(scrape_announcements())

    assert len(docs) == len(rows)
    first = docs[0]
    assert first.type == "announcement"
    assert first.source == "official"
    assert first.url == rows[0]["link"]
    assert "<p>" not in first.content


def test_scrape_announcements_stops_at_the_configured_limit():
    """The listing is newest-first, so a limit caps this to the N most recent
    announcements — verified here against a fake 5-row listing, no live network."""
    fake_rows = [_row(f"item-{i}") for i in range(5)]

    with (
        patch.object(announcements, "make_client"),
        patch.object(announcements, "get", return_value=_paged_response(fake_rows)),
        patch.object(announcements, "get_setting_cached", return_value=2),
    ):
        docs = list(scrape_announcements())

    assert [d.url for d in docs] == [
        "https://finki.ukim.mk/announcements/item-0/",
        "https://finki.ukim.mk/announcements/item-1/",
    ]


def test_scrape_announcements_unlimited_by_default():
    fake_rows = [_row(f"item-{i}") for i in range(5)]

    with (
        patch.object(announcements, "make_client"),
        patch.object(announcements, "get", return_value=_paged_response(fake_rows)),
        patch.object(announcements, "get_setting_cached", return_value=None),
    ):
        docs = list(scrape_announcements())

    assert len(docs) == 5


def test_scrape_announcements_incremental_skips_known_and_stops_after_a_run_of_them():
    # stops after INCREMENTAL_STOP_AFTER_KNOWN known posts in a row
    total = announcements.INCREMENTAL_STOP_AFTER_KNOWN + 20
    fake_rows = [_row(f"item-{i}") for i in range(total)]
    # first two are new, everything after is already indexed
    known = {row["link"] for row in fake_rows[2:]}

    with (
        patch.object(announcements, "make_client"),
        patch.object(announcements, "get", return_value=_paged_response(fake_rows)) as mock_get,
        patch.object(announcements, "get_setting_cached", return_value=None),
    ):
        docs = list(scrape_announcements(skip_urls=known))

    assert [d.url for d in docs] == [
        "https://finki.ukim.mk/announcements/item-0/",
        "https://finki.ukim.mk/announcements/item-1/",
    ]
    assert mock_get.call_count == 1


def test_scrape_announcements_paginates_lazily_and_stops_once_the_limit_is_reached():
    # the limit is reached on page 1, so page 2 is never requested
    page1 = [_row("a"), _row("b")]
    page2 = [_row("c")]
    responses = [
        MagicMock(headers={"X-WP-TotalPages": "2"}, json=MagicMock(return_value=page1)),
        MagicMock(headers={"X-WP-TotalPages": "2"}, json=MagicMock(return_value=page2)),
    ]

    with (
        patch.object(announcements, "make_client"),
        patch.object(announcements, "get", side_effect=responses) as mock_get,
        patch.object(announcements, "get_setting_cached", return_value=1),
    ):
        docs = list(scrape_announcements())

    assert [d.url for d in docs] == ["https://finki.ukim.mk/announcements/a/"]
    assert mock_get.call_count == 1
