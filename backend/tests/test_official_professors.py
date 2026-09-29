from pathlib import Path
from unittest.mock import patch

from backend.scrapers.official_site import professors
from backend.scrapers.official_site.professors import parse_listing_html, parse_professor_html, scrape_professors

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_listing_html_extracts_profile_urls_and_dedupes():
    html = """
    <div class="kadar-list">
        <a class="kadar-item__link" href="https://finki.ukim.mk/kadar/full/">Полн Профил</a>
        <a class="kadar-item__link" href="https://finki.ukim.mk/kadar/empty/">Празен Профил</a>
        <a class="kadar-item__link" href="https://finki.ukim.mk/kadar/full/">Полн Профил</a>
        <a class="some-other-link" href="https://finki.ukim.mk/kadar/?kat=docenti">Доценти</a>
    </div>
    """
    assert parse_listing_html(html) == [
        "https://finki.ukim.mk/kadar/full/",
        "https://finki.ukim.mk/kadar/empty/",
    ]


def test_parse_professor_html_extracts_name_content_and_email():
    html = (FIXTURES / "official_professor.html").read_text(encoding="utf-8")
    name, content, email = parse_professor_html(html)

    assert name == "д-р Марјан Гушев"
    assert "Универзитетот Св. Кирил и Методиј" in content
    assert email == "marjan.gusev@finki.ukim.mk"


def test_parse_professor_html_missing_content_returns_empty():
    name, content, email = parse_professor_html("<html><body>nothing here</body></html>")
    assert (name, content, email) == ("", "", None)


def test_scrape_professors_skips_only_truly_empty_profiles():
    # no bio but an email -> keep; neither -> skip
    fake_urls = [
        "https://finki.ukim.mk/kadar/full/",
        "https://finki.ukim.mk/kadar/contact-only/",
        "https://finki.ukim.mk/kadar/empty/",
    ]

    with (
        patch.object(professors, "make_client"),
        patch.object(professors, "get") as mock_get,
        patch.object(professors, "parse_listing_html", return_value=fake_urls),
        patch.object(
            professors,
            "parse_professor_html",
            side_effect=[
                ("Полн Профил", "Богата биографија. " * 10, "full@finki.ukim.mk"),
                ("Само Контакт", "Нема внесени податоци", "contact@finki.ukim.mk"),
                ("Празен Профил", "Нема внесени податоци", None),
            ],
        ),
    ):
        mock_get.return_value.content = b""
        mock_get.return_value.url.path = "/kadar/full/"
        docs = list(scrape_professors())

    assert [d.url for d in docs] == [
        "https://finki.ukim.mk/kadar/full/",
        "https://finki.ukim.mk/kadar/contact-only/",
    ]
    assert docs[0].type == "professor"
    assert docs[0].metadata == {"email": "full@finki.ukim.mk"}
    assert docs[1].metadata == {"email": "contact@finki.ukim.mk"}


def test_scrape_professors_incremental_does_not_fetch_known_profiles():
    fake_urls = [
        "https://finki.ukim.mk/kadar/new/",
        "https://finki.ukim.mk/kadar/known/",
    ]

    with (
        patch.object(professors, "make_client"),
        patch.object(professors, "get") as mock_get,
        patch.object(professors, "parse_listing_html", return_value=fake_urls),
        patch.object(
            professors,
            "parse_professor_html",
            return_value=("Нов Профил", "Богата биографија. " * 10, "new@finki.ukim.mk"),
        ),
    ):
        mock_get.return_value.content = b""
        mock_get.return_value.url.path = "/kadar/new/"
        docs = list(scrape_professors(skip_urls={"https://finki.ukim.mk/kadar/known/"}))

    assert [d.url for d in docs] == ["https://finki.ukim.mk/kadar/new/"]
    # listing fetch + the one new profile — the known profile was never requested
    assert mock_get.call_count == 2
