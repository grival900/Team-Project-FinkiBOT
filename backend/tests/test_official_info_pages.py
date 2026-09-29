from unittest.mock import patch

from backend.scrapers.official_site import info_pages
from backend.scrapers.official_site.info_pages import parse_info_page_html, scrape_info_pages


def test_parse_info_page_html_reads_generic_template():
    html = """
    <html><body>
    <h1>Деканат</h1>
    <div class="page-content__body">
        <div class="addtoany_share_save_container">share buttons</div>
        <p>д-р Петре Ламески, декан</p>
    </div>
    </body></html>
    """
    title, content = parse_info_page_html(html)
    assert title == "Деканат"
    assert "д-р Петре Ламески" in content
    assert "share buttons" not in content


def test_parse_info_page_html_falls_back_across_templates():
    """The site doesn't share one template across these pages — confirmed live across
    ~30 pages — so the extractor tries several selectors in priority order."""
    html = """
    <html><body>
    <h1>Институти и Центри</h1>
    <div class="page-content"><p>содржина во sidebar-layout шаблон</p></div>
    </body></html>
    """
    title, content = parse_info_page_html(html)
    assert title == "Институти и Центри"
    assert "sidebar-layout" in content


def test_parse_info_page_html_missing_content_returns_empty():
    title, content = parse_info_page_html("<html><body><h1>Насловpage</h1></body></html>")
    assert content == ""


def test_scrape_info_pages_skips_near_empty_pages():
    fake_urls = ["/a/", "/b/"]

    with (
        patch.object(info_pages, "PAGE_URLS", fake_urls),
        patch.object(info_pages, "make_client"),
        patch.object(info_pages, "get") as mock_get,
        patch.object(
            info_pages,
            "parse_info_page_html",
            side_effect=[
                ("Целосна страница", "Богата содржина. " * 10),
                ("Празна страница", "Кратко"),
            ],
        ),
    ):
        mock_get.return_value.content = b""
        docs = list(scrape_info_pages())

    assert [d.title for d in docs] == ["Целосна страница"]
    assert docs[0].type == "page"
    assert docs[0].source == "official"
