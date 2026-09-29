from bs4 import BeautifulSoup, Tag

BASE_URL = "https://finki.ukim.mk"


def element_to_text(el: Tag) -> str:
    text = el.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def parse_html(content: bytes | str) -> BeautifulSoup:
    return BeautifulSoup(content, "lxml")


def parse_xml(content: bytes | str) -> BeautifulSoup:
    return BeautifulSoup(content, "xml")


def extract_page_body_text(soup: BeautifulSoup) -> str:
    """Text of a `.page-content__body`, without the share buttons at the top."""
    body_el = soup.select_one(".page-content__body")
    if body_el is None:
        return ""
    share_widget = body_el.select_one(".addtoany_share_save_container")
    if share_widget is not None:
        share_widget.decompose()
    return element_to_text(body_el)


# The info pages use different templates, so try these in order.
INFO_PAGE_CONTENT_SELECTORS = [".page-content__body", ".kadar-content", ".page-content", ".contact-page"]


def extract_info_page_text(soup: BeautifulSoup) -> str:
    for selector in INFO_PAGE_CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el is None:
            continue
        share_widget = el.select_one(".addtoany_share_save_container")
        if share_widget is not None:
            share_widget.decompose()
        return element_to_text(el)
    return ""
