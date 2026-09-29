import secrets

from sqlalchemy.orm import Session

from backend.models import Subscription


def create_subscription(db: Session, email: str, keywords: list[str], course_codes: list[str]) -> Subscription:
    sub = Subscription(
        email=email,
        filters={"keywords": keywords, "course_codes": course_codes},
        confirmed=False,
        confirm_token=secrets.token_urlsafe(32),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def confirm_subscription(db: Session, token: str) -> Subscription | None:
    sub = db.query(Subscription).filter_by(confirm_token=token).one_or_none()
    if sub is None:
        return None
    sub.confirmed = True
    db.commit()
    return sub
