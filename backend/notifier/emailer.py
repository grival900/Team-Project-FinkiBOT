import html
import smtplib
from email.mime.text import MIMEText

from backend.core.config import get_settings
from backend.models import Document


def send_email(to: str, subject: str, html_body: str) -> None:
    settings = get_settings()
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


def send_confirmation_email(to: str, confirm_url: str) -> None:
    body = (
        "<p>Потврди ја претплатата за известувања за нови соопштенија на ФИНКИ.</p>"
        f'<p><a href="{html.escape(confirm_url, quote=True)}">Потврди претплата</a></p>'
        "<p>Ако не си побарал ова, слободно игнорирај ја пораката.</p>"
    )
    send_email(to, "Потврди претплата — FinkiBOT", body)


def send_announcement_email(to: str, documents: list[Document]) -> None:
    # scraped titles/URLs, so escape them before putting them in HTML
    items = "".join(
        f'<li><a href="{html.escape(d.url, quote=True)}">{html.escape(d.title)}</a></li>'
        for d in documents
    )
    body = f"<p>Нови соопштенија на ФИНКИ:</p><ul>{items}</ul>"
    send_email(to, "Нови соопштенија на ФИНКИ", body)


def send_password_reset_email(to: str, reset_url: str) -> None:
    body = (
        "<p>Администратор побара ресетирање на лозинката за твојата сметка на FinkiBOT.</p>"
        f'<p><a href="{html.escape(reset_url, quote=True)}">Постави нова лозинка</a></p>'
        "<p>Ако не си побарал ова, слободно игнорирај ја пораката.</p>"
    )
    send_email(to, "Ресетирање лозинка — FinkiBOT", body)
