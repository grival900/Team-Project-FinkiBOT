import logging

from backend.db import SessionLocal
from backend.models import SentNotification, Subscription
from backend.notifier.diff import find_unsent_matches
from backend.notifier.emailer import send_announcement_email

logger = logging.getLogger(__name__)


def run_notification_job() -> int:
    """Emails each confirmed subscriber the new matching announcements. Sent ones are
    recorded in `sent_notifications`, so nothing is sent twice."""
    notified = 0
    with SessionLocal() as db:
        subscriptions = db.query(Subscription).filter_by(confirmed=True).all()
        for sub in subscriptions:
            matches = find_unsent_matches(db, sub)
            if not matches:
                continue
            try:
                send_announcement_email(sub.email, matches)
            except Exception:
                logger.exception("Failed to send notification email to %s", sub.email)
                continue
            for doc in matches:
                db.add(SentNotification(subscription_id=sub.id, document_id=doc.id))
            notified += len(matches)
        db.commit()
    return notified
