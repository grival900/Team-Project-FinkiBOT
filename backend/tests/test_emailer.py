from dataclasses import dataclass
from unittest.mock import patch

from backend.notifier import emailer


@dataclass
class FakeDoc:
    title: str
    url: str


def _sent():
    """Patch out the SMTP-touching send_email and capture its (to, subject, body)."""
    return patch.object(emailer, "send_email")


def test_announcement_email_lists_every_document_as_a_link():
    docs = [
        FakeDoc(title="Резултати по ДС", url="https://finki.ukim.mk/a/1"),
        FakeDoc(title="Термин за колоквиум", url="https://finki.ukim.mk/a/2"),
    ]
    with _sent() as send_email:
        emailer.send_announcement_email("student@example.com", docs)

    to, subject, body = send_email.call_args.args
    assert to == "student@example.com"
    assert subject == "Нови соопштенија на ФИНКИ"
    assert body.count("<li>") == 2
    assert '<a href="https://finki.ukim.mk/a/1">Резултати по ДС</a>' in body
    assert '<a href="https://finki.ukim.mk/a/2">Термин за колоквиум</a>' in body


def test_announcement_email_with_no_documents_still_produces_valid_markup():
    """The job guards against this, but the function shouldn't crash or emit `<li>`s."""
    with _sent() as send_email:
        emailer.send_announcement_email("student@example.com", [])

    _, _, body = send_email.call_args.args
    assert "<ul></ul>" in body
    assert "<li>" not in body


def test_announcement_email_escapes_html_in_titles():
    """Announcement titles are scraped from external HTML — a `<` or `&` in one must
    not break out of the surrounding markup in the email."""
    docs = [FakeDoc(title="Q&A: <b>важно</b> за испит", url="https://finki.ukim.mk/a/1")]
    with _sent() as send_email:
        emailer.send_announcement_email("student@example.com", docs)

    _, _, body = send_email.call_args.args
    assert "<b>важно</b>" not in body
    assert "Q&amp;A: &lt;b&gt;важно&lt;/b&gt;" in body


def test_announcement_email_escapes_quotes_in_urls():
    docs = [FakeDoc(title="Соопштение", url='https://finki.ukim.mk/a/1"><script>x</script>')]
    with _sent() as send_email:
        emailer.send_announcement_email("student@example.com", docs)

    _, _, body = send_email.call_args.args
    assert "<script>" not in body
    assert "&quot;&gt;&lt;script&gt;" in body


def test_confirmation_email_escapes_the_url():
    with _sent() as send_email:
        emailer.send_confirmation_email("s@example.com", 'https://x/confirm?token=a"b&c')

    _, subject, body = send_email.call_args.args
    assert subject == "Потврди претплата — FinkiBOT"
    assert 'token=a"b&c' not in body
    assert "token=a&quot;b&amp;c" in body


def test_password_reset_email_escapes_the_url():
    with _sent() as send_email:
        emailer.send_password_reset_email("s@example.com", 'https://x/reset?token=a"b&c')

    _, subject, body = send_email.call_args.args
    assert subject == "Ресетирање лозинка — FinkiBOT"
    assert "token=a&quot;b&amp;c" in body
