from pathlib import Path

from backend.scrapers.finki_hub.recordings import parse_course_links, parse_course_page_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_course_links_dedupes_and_returns_absolute_urls():
    html = (FIXTURES / "finki_hub_recordings_intro.html").read_text(encoding="utf-8")
    urls = parse_course_links(html)

    assert urls == [
        "https://snimki.finki-hub.com/courses/semester-1/matematika-1.html",
        "https://snimki.finki-hub.com/courses/semester-1/strukturno-programiranje.html",
    ]


def test_parse_course_page_html_extracts_title_and_strips_anchor_markers():
    html = (FIXTURES / "finki_hub_recordings_course.html").read_text(encoding="utf-8")
    title, content = parse_course_page_html(html)

    assert title == "Математика 1"
    assert "## Предавања" in content
    assert "### Весна Димитрова, 2021" in content
    assert "​" not in content  # zero-width-space anchor markers must be stripped


def test_parse_course_page_html_preserves_recording_links_as_markdown():
    # recording links must be kept as markdown links
    html = (FIXTURES / "finki_hub_recordings_course.html").read_text(encoding="utf-8")
    _, content = parse_course_page_html(html)

    assert "- [Предавање 1](https://youtube.com/watch?v=1)" in content
    assert "- [Предавање 2](https://youtube.com/watch?v=2)" in content


def test_parse_course_page_html_keeps_plain_text_for_sections_with_no_links():
    html = (FIXTURES / "finki_hub_recordings_course.html").read_text(encoding="utf-8")
    _, content = parse_course_page_html(html)

    assert "## Белешки" in content
    assert "Нема" in content


def test_parse_course_page_html_includes_course_name_in_content():
    # only content is embedded, so the course name has to be in it
    html = (FIXTURES / "finki_hub_recordings_course.html").read_text(encoding="utf-8")
    title, content = parse_course_page_html(html)

    assert title in content


def test_parse_course_page_html_missing_doc_returns_empty():
    title, content = parse_course_page_html("<html><body>no vp-doc here</body></html>")
    assert title == ""
    assert content == ""
