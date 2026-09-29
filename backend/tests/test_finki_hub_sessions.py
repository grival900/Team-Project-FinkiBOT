from datetime import datetime
from unittest.mock import patch

import httpx

from backend.scrapers.finki_hub import sessions
from backend.scrapers.finki_hub.sessions import extract_session_file_content, parse_session_entry, scrape_sessions


def test_parse_session_entry_extracts_fields():
    title, content, metadata = parse_session_entry("2025/2026 Јуни", "jun_2025_2026.xlsx")
    assert title == "2025/2026 Јуни"
    assert "jun_2025_2026.xlsx" in content
    assert "assets.finki-hub.com/sessions/jun_2025_2026.xlsx" in content
    assert metadata["filename"] == "jun_2025_2026.xlsx"
    assert metadata["academic_year"] == "2025/2026"
    assert metadata["session_type"] == "Јуни"


def test_parse_session_entry_colloquium():
    title, content, metadata = parse_session_entry(
        "2024/2025 Зимски - Прв Колоквиум", "zimski_kol_1_2024_2025.xlsx"
    )
    assert metadata["academic_year"] == "2024/2025"
    assert metadata["session_type"] == "Зимски - Прв Колоквиум"


def test_parse_session_entry_includes_download_link():
    _, content, _ = parse_session_entry("2024/2025 Јуни", "jun_2024_2025.xlsx")
    assert "Линк за преземање: https://assets.finki-hub.com/sessions/jun_2024_2025.xlsx" in content


def test_extract_session_file_content_dispatches_by_extension():
    with patch.object(
        sessions, "extract_xlsx_schedule_grid", return_value=("xlsx text", datetime(2026, 6, 8))
    ) as mock_xlsx:
        assert extract_session_file_content("jun_2025_2026.xlsx", b"data") == ("xlsx text", datetime(2026, 6, 8))
        mock_xlsx.assert_called_once_with(b"data")

    with patch.object(sessions, "extract_pdf_text", return_value="pdf text") as mock_pdf:
        # No date signal in the older PDF format, unlike xlsx.
        assert extract_session_file_content("jan_2021_2022.pdf", b"data") == ("pdf text", None)
        mock_pdf.assert_called_once_with(b"data")


def test_extract_session_file_content_unknown_extension_returns_empty():
    assert extract_session_file_content("weird.docx", b"data") == ("", None)


def test_scrape_sessions_appends_extracted_file_content_and_published_at():
    fake_data = {"2025/2026 Јуни": "jun_2025_2026.xlsx"}

    with (
        patch.object(sessions, "make_client") as mock_make_client,
        patch.object(sessions, "get") as mock_get,
        patch.object(
            sessions,
            "extract_session_file_content",
            return_value=("08.06.2026 08:00 117: Тест", datetime(2026, 6, 8)),
        ),
    ):
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.return_value.json.return_value = fake_data
        mock_get.return_value.content = b"xlsx bytes"
        docs = list(scrape_sessions())

    assert len(docs) == 1
    assert "Линк за преземање:" in docs[0].content
    assert "08.06.2026 08:00 117: Тест" in docs[0].content
    assert docs[0].published_at == datetime(2026, 6, 8)


def test_scrape_sessions_skips_entry_entirely_on_fetch_failure():
    # a failed download must not overwrite the version we already have
    fake_data = {"2025/2026 Јуни": "jun_2025_2026.xlsx"}

    with (
        patch.object(sessions, "make_client") as mock_make_client,
        patch.object(sessions, "get") as mock_get,
    ):
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.return_value.json.return_value = fake_data
        mock_get.side_effect = httpx.HTTPError("boom")
        docs = list(scrape_sessions())

    assert docs == []


def test_scrape_sessions_skips_entry_entirely_on_parse_failure():
    # same for a file that fails to parse
    fake_data = {"2025/2026 Јуни": "jun_2025_2026.xlsx"}

    with (
        patch.object(sessions, "make_client") as mock_make_client,
        patch.object(sessions, "get") as mock_get,
        patch.object(sessions, "extract_session_file_content", side_effect=ValueError("corrupt file")),
    ):
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.return_value.json.return_value = fake_data
        mock_get.return_value.content = b"corrupt bytes"
        docs = list(scrape_sessions())

    assert docs == []
