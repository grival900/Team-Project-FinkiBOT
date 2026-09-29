from backend.scrapers.official_site.linked_documents import (
    build_document,
    document_title,
    is_allowed,
    page_content_html,
    pdf_links,
)

_PAGE = "https://finki.ukim.mk/studii-2/vidovi-studii/doktorski-studii/"


def test_pdf_links_resolves_relative_links_and_drops_query_strings():
    html = """
    <p><a href="/wp-content/uploads/2025/12/elaborat.pdf?ver=2">Елаборат</a></p>
    <p><a href="https://ukim.edu.mk/wp-content/uploads/pravilnik.PDF">Правилник</a></p>
    <p><a href="/kontakt/">not a pdf</a> <a href="mailto:x@finki.ukim.mk">mail</a></p>
    """

    assert pdf_links(html, _PAGE) == [
        ("https://finki.ukim.mk/wp-content/uploads/2025/12/elaborat.pdf", "Елаборат"),
        ("https://ukim.edu.mk/wp-content/uploads/pravilnik.PDF", "Правилник"),
    ]


def test_a_broken_link_is_not_allowed():
    # a real (mistyped) link on the doctoral studies page - its host parses as "https"
    [(url, _)] = pdf_links('<a href="http://https//flf.ukim.mk/x.pdf">x</a>', _PAGE)
    assert not is_allowed(url)


def test_page_content_html_leaves_out_the_menu():
    page = """
    <nav><a href="/menu.pdf">menu</a></nav>
    <div class="page-content__body"><a href="/body.pdf">body</a></div>
    """

    assert [u for u, _ in pdf_links(page_content_html(page), _PAGE)] == ["https://finki.ukim.mk/body.pdf"]


def test_is_allowed_only_for_finki_and_ukim():
    assert is_allowed("https://finki.ukim.mk/a.pdf")
    assert is_allowed("https://www.ukim.edu.mk/a.pdf")
    assert not is_allowed("https://www.akvo.mk/a.pdf")
    assert not is_allowed("https://notukim.edu.mk.evil.com/a.pdf")


def test_document_title_falls_back_to_the_file_name_for_vague_link_text():
    url = "https://ukim.edu.mk/wp-content/uploads/pravilnik-iii_ciklus-31.12.2020.pdf"

    assert document_title("Правилник за трет циклус", url) == "Правилник за трет циклус"
    assert document_title("овде", url) == "pravilnik iii ciklus 31.12.2020"


def test_build_document_keeps_the_parent_page():
    info = {"title": "Правилник", "parent_url": _PAGE, "parent_title": "Докторски студии"}

    doc = build_document("https://ukim.edu.mk/p.pdf", info, "Член 45 Ментор на докторски труд може да биде ...")

    assert (doc.source, doc.type, doc.url) == ("official", "document", "https://ukim.edu.mk/p.pdf")
    assert doc.content.startswith("Документ: Правилник\nОбјавен на страницата: Докторски студии")
    assert doc.metadata["parent_url"] == _PAGE
