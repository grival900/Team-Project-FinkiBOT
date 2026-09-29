from pathlib import Path

from backend.scrapers.official_site.schedule_links import parse_schedule_links_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_schedule_links_html_extracts_exam_session_link():
    html = (FIXTURES / "schedule_links_widget.html").read_text(encoding="utf-8")
    links = parse_schedule_links_html(html)

    titles = [title for title, _url in links]
    assert any("јунска испитна сесија" in title for title in titles)
    urls = [url for _title, url in links]
    assert "https://finkiukim-my.sharepoint.com/:x:/g/personal/x/june-2026" in urls


def test_parse_schedule_links_html_extracts_map_link_without_subtitle():
    html = (FIXTURES / "schedule_links_widget.html").read_text(encoding="utf-8")
    links = parse_schedule_links_html(html)

    assert ("ФИНКИ Live Мапа", "https://live.finki.ukim.mk/") in links


def test_parse_schedule_links_html_missing_section_returns_empty():
    assert parse_schedule_links_html("<html><body>no widget here</body></html>") == []
