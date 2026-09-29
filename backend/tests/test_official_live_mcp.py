import json
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.mcp_servers.official_live_mcp import server
from backend.mcp_servers.official_live_mcp.server import parse_wp_search_response, search_official_site_live

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_wp_search_response_extracts_title_url_type_subtype():
    data = json.loads((FIXTURES / "wp_search_response.json").read_text(encoding="utf-8"))
    results = parse_wp_search_response(data)

    assert len(results) == 5
    first = results[0]
    assert first["title"] == "Распоред за септемвриска испитна сесија"
    assert first["url"] == "https://finki.ukim.mk/schedule/raspored-za-septemvriska-ispitna-sesija/"
    assert first["type"] == "post"
    assert first["subtype"] == "schedule"


def test_parse_wp_search_response_empty_list():
    assert parse_wp_search_response([]) == []


def test_search_official_site_live_returns_parsed_results():
    fake_results = [{"title": "Тест", "url": "https://finki.ukim.mk/x/", "type": "post", "subtype": "announcement"}]

    with patch.object(server, "make_client") as mock_make_client:
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.return_value.json.return_value = fake_results

        results = search_official_site_live("испитна сесија", limit=3)

    assert results == fake_results
    _, kwargs = mock_client.get.call_args
    assert kwargs["params"] == {"search": "испитна сесија", "per_page": 3}


def test_search_official_site_live_returns_empty_list_on_http_error():
    with patch.object(server, "make_client") as mock_make_client:
        mock_client = mock_make_client.return_value.__enter__.return_value
        mock_client.get.side_effect = httpx.HTTPError("boom")

        assert search_official_site_live("испитна сесија") == []
