from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.schemas import SearchResultOut
from backend.core.retrieval import search
from backend.db import get_db

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResultOut])
def search_documents(
    q: str,
    source: str | None = None,
    type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> list[SearchResultOut]:
    """`limit` is per source. A date range only matches dated documents (announcements)."""
    results = search(db, q, k=limit, source=source, type=type, date_from=date_from, date_to=date_to)
    return [SearchResultOut(**r.__dict__) for r in results]
