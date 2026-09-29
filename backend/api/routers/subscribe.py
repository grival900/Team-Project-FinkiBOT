from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.api.schemas import SubscribeRequest
from backend.core.config import get_settings
from backend.db import get_db
from backend.notifier.emailer import send_confirmation_email
from backend.notifier.subscriptions import confirm_subscription, create_subscription

router = APIRouter(prefix="/announcements", tags=["subscribe"])
settings = get_settings()


@router.post("/subscribe", status_code=201)
def subscribe(payload: SubscribeRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    sub = create_subscription(db, payload.email, payload.keywords, payload.course_codes)
    confirm_url = f"{settings.app_base_url}/announcements/confirm?token={sub.confirm_token}"
    send_confirmation_email(payload.email, confirm_url)
    return {"status": "pending_confirmation"}


@router.get("/confirm", response_class=HTMLResponse)
def confirm(token: str, db: Session = Depends(get_db)) -> str:
    sub = confirm_subscription(db, token)
    if sub is None:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    return "<p>Претплатата е потврдена. Ќе добивате е-пошта за нови соопштенија.</p>"
