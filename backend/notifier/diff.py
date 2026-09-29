from sqlalchemy.orm import Session

from backend.models import Document, SentNotification, Subscription


def matches_filters(doc: Document, filters: dict | None) -> bool:
    """Keywords and course codes are both matched as case-insensitive text in the
    title and content. No terms = every announcement matches. Blank terms are dropped
    first, since "" would match everything."""
    raw_terms = [*(filters or {}).get("keywords", []), *(filters or {}).get("course_codes", [])]
    terms = [stripped for t in raw_terms if (stripped := t.strip().lower())]
    if not terms:
        return True
    haystack = f"{doc.title}\n{doc.content}".lower()
    return any(term in haystack for term in terms)


def find_unsent_matches(db: Session, subscription: Subscription) -> list[Document]:
    already_sent_ids = {
        row.document_id
        for row in db.query(SentNotification.document_id).filter_by(subscription_id=subscription.id)
    }
    announcements = db.query(Document).filter_by(source="official", type="announcement").all()
    return [
        doc
        for doc in announcements
        if doc.id not in already_sent_ids and matches_filters(doc, subscription.filters)
    ]
