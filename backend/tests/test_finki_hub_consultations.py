from pathlib import Path
from unittest.mock import patch

import httpx

from backend.scrapers.finki_hub import consultations
from backend.scrapers.finki_hub.consultations import parse_consultations_html, scrape_consultations

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_consultations_html_extracts_scheduled_slots():
    html = (FIXTURES / "consultations_with_slots.html").read_text(encoding="utf-8")
    content = parse_consultations_html(html)

    assert "Датум: 14.9.2026 (понеделник)" in content
    assert "Време: 11:00 - 13:00" in content
    assert "Локација: M8" in content
    # Only the fields relevant to "when/where" are kept, not e.g. attendee count.
    assert "Пријавени студенти" not in content


def test_parse_consultations_html_no_slots_scheduled():
    html = (FIXTURES / "consultations_empty.html").read_text(encoding="utf-8")
    content = parse_consultations_html(html)

    assert content == (
        "Нема закажани консултации. Ве молиме контактирајте го професорот по е-пошта за да договорите термин."
    )


def test_scrape_consultations_builds_documents_for_active_staff_with_a_link():
    fake_entries = [
        {"name": "Активен", "active": "1", "consultations": "https://consultations.finki.ukim.mk/display/aktiven"},
        {"name": "Неактивен", "active": "0", "consultations": "https://consultations.finki.ukim.mk/display/staro"},
        {"name": "Без линк", "active": "1"},
    ]

    with (
        patch.object(consultations, "make_client") as mock_make_client,
        patch.object(consultations, "get") as mock_get,
        patch.object(consultations, "parse_consultations_html", return_value="Датум: 1.1.2027, Време: 10:00 - 11:00"),
    ):
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.return_value.json.return_value = fake_entries
        docs = list(scrape_consultations())

    assert [d.title for d in docs] == ["Активен"]
    assert [d.url for d in docs] == ["https://consultations.finki.ukim.mk/display/aktiven"]
    assert docs[0].type == "consultation"
    assert "Датум: 1.1.2027" in docs[0].content
    mock_get.assert_called_once_with(mock_client, "https://consultations.finki.ukim.mk/display/aktiven")


def test_scrape_consultations_skips_known_urls_incrementally():
    fake_entries = [
        {"name": "Нов", "active": "1", "consultations": "https://consultations.finki.ukim.mk/display/nov"},
        {"name": "Познат", "active": "1", "consultations": "https://consultations.finki.ukim.mk/display/poznat"},
    ]

    with (
        patch.object(consultations, "make_client") as mock_make_client,
        patch.object(consultations, "get") as mock_get,
        patch.object(consultations, "parse_consultations_html", return_value="Нема закажани консултации."),
    ):
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.return_value.json.return_value = fake_entries
        docs = list(scrape_consultations(skip_urls={"https://consultations.finki.ukim.mk/display/poznat"}))

    assert [d.url for d in docs] == ["https://consultations.finki.ukim.mk/display/nov"]
    mock_get.assert_called_once()


def test_scrape_consultations_logs_and_continues_on_fetch_failure():
    fake_entries = [
        {"name": "Паѓа", "active": "1", "consultations": "https://consultations.finki.ukim.mk/display/pagja"},
        {"name": "Работи", "active": "1", "consultations": "https://consultations.finki.ukim.mk/display/rabo"},
    ]

    with (
        patch.object(consultations, "make_client") as mock_make_client,
        patch.object(consultations, "get") as mock_get,
        patch.object(consultations, "parse_consultations_html", return_value="Датум: 2.2.2027"),
    ):
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.return_value.json.return_value = fake_entries
        mock_get.side_effect = [httpx.HTTPError("boom"), mock_client.get.return_value]
        docs = list(scrape_consultations())

    assert [d.title for d in docs] == ["Работи"]
