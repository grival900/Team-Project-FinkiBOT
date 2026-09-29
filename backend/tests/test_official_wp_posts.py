import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from backend.scrapers.official_site import wp_posts
from backend.scrapers.official_site.wp_posts import (
    parse_wp_post_row,
    scrape_events,
    scrape_jobs_and_internships,
    scrape_projects,
    scrape_wp_post_type,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_wp_post_row_extracts_title_url_content_and_date():
    row = _load("wp_event_response.json")[0]
    title, url, content, date_text = parse_wp_post_row(row)

    assert title == "ФИНКИ се грижи за своите студенти!"
    assert url == "https://finki.ukim.mk/events/finki-se-grizhi-za-svoite-studenti/"
    assert "ФОКУС Лаб" in content
    assert "<p>" not in content
    assert date_text == "2026-06-06T10:32:00"


def test_parse_wp_post_row_unescapes_html_entities_in_the_title():
    # WordPress HTML-encodes titles ("&#8211;")
    row = {"title": {"rendered": "VEZILKA &#8211; North Macedonia&#8217;s Antenna"}, "link": "https://x/", "content": {"rendered": "<p>x</p>"}}
    title, _, _, _ = parse_wp_post_row(row)

    assert title == "VEZILKA – North Macedonia’s Antenna"


def test_parse_wp_post_row_handles_missing_link_and_content():
    title, url, content, date_text = parse_wp_post_row({"title": {"rendered": "Наслов"}})

    assert title == "Наслов"
    assert url == ""
    assert content == ""
    assert date_text is None


def test_scrape_wp_post_type_paginates_using_x_wp_totalpages():
    """Two pages of one row each — the loop must keep going past page 1 because
    X-WP-TotalPages says 2, then stop once it reaches that count."""
    page1 = [{"link": "https://finki.ukim.mk/event/a/", "title": {"rendered": "A"}, "content": {"rendered": "<p>a</p>"}, "date": "2026-01-01T00:00:00"}]
    page2 = [{"link": "https://finki.ukim.mk/event/b/", "title": {"rendered": "B"}, "content": {"rendered": "<p>b</p>"}, "date": "2026-01-02T00:00:00"}]

    responses = [
        MagicMock(headers={"X-WP-TotalPages": "2"}, json=MagicMock(return_value=page1)),
        MagicMock(headers={"X-WP-TotalPages": "2"}, json=MagicMock(return_value=page2)),
    ]

    with (
        patch.object(wp_posts, "make_client"),
        patch.object(wp_posts, "get", side_effect=responses) as mock_get,
    ):
        docs = list(scrape_wp_post_type("event", "event"))

    assert [d.title for d in docs] == ["A", "B"]
    assert mock_get.call_count == 2


def test_scrape_wp_post_type_skips_known_urls():
    page1 = [
        {"link": "https://finki.ukim.mk/event/a/", "title": {"rendered": "A"}, "content": {"rendered": "<p>a</p>"}, "date": None},
        {"link": "https://finki.ukim.mk/event/b/", "title": {"rendered": "B"}, "content": {"rendered": "<p>b</p>"}, "date": None},
    ]
    response = MagicMock(headers={"X-WP-TotalPages": "1"}, json=MagicMock(return_value=page1))

    with (
        patch.object(wp_posts, "make_client"),
        patch.object(wp_posts, "get", return_value=response),
    ):
        docs = list(scrape_wp_post_type("event", "event", skip_urls={"https://finki.ukim.mk/event/a/"}))

    assert [d.title for d in docs] == ["B"]


def test_scrape_wp_post_type_skips_rows_with_no_content():
    # posts with empty content are skipped
    page1 = [{"link": "https://finki.ukim.mk/event/a/", "title": {"rendered": "A"}, "content": {"rendered": ""}, "date": None}]
    response = MagicMock(headers={"X-WP-TotalPages": "1"}, json=MagicMock(return_value=page1))

    with (
        patch.object(wp_posts, "make_client"),
        patch.object(wp_posts, "get", return_value=response),
    ):
        docs = list(scrape_wp_post_type("event", "event"))

    assert docs == []


def test_scrape_wp_post_type_returns_empty_on_http_error():
    with (
        patch.object(wp_posts, "make_client"),
        patch.object(wp_posts, "get", side_effect=httpx.HTTPError("boom")),
    ):
        assert list(scrape_wp_post_type("event", "event")) == []


def test_scrape_events_uses_the_event_rest_base_and_event_doc_type():
    row = _load("wp_event_response.json")[:1]
    response = MagicMock(headers={"X-WP-TotalPages": "1"}, json=MagicMock(return_value=row))

    with (
        patch.object(wp_posts, "make_client"),
        patch.object(wp_posts, "get", return_value=response) as mock_get,
    ):
        docs = list(scrape_events())

    assert docs[0].type == "event"
    assert docs[0].source == "official"
    assert "/wp-json/wp/v2/event?" in mock_get.call_args[0][1]


def test_scrape_projects_uses_the_project_rest_base_and_project_doc_type():
    row = _load("wp_project_response.json")[:1]
    response = MagicMock(headers={"X-WP-TotalPages": "1"}, json=MagicMock(return_value=row))

    with (
        patch.object(wp_posts, "make_client"),
        patch.object(wp_posts, "get", return_value=response) as mock_get,
    ):
        docs = list(scrape_projects())

    assert docs[0].type == "project"
    assert "/wp-json/wp/v2/project?" in mock_get.call_args[0][1]


def test_scrape_jobs_and_internships_uses_the_jobs_rest_base_and_job_doc_type():
    row = _load("wp_jobs_response.json")[:1]
    response = MagicMock(headers={"X-WP-TotalPages": "1"}, json=MagicMock(return_value=row))

    with (
        patch.object(wp_posts, "make_client"),
        patch.object(wp_posts, "get", return_value=response) as mock_get,
    ):
        docs = list(scrape_jobs_and_internships())

    assert docs[0].type == "job"
    assert "/wp-json/wp/v2/jobs-and-internships?" in mock_get.call_args[0][1]
