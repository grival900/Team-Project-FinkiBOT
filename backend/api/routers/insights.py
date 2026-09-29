from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.schemas import InsightsOut
from backend.core.insights import (
    announcements_by_month,
    course_semester_distribution,
    course_tag_counts,
    documents_by_type,
)
from backend.db import get_db

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightsOut)
def get_insights(db: Session = Depends(get_db)) -> InsightsOut:
    """Aggregate stats over already-indexed data — no new scraping, no LLM calls,
    backs the frontend's FINKI Insights dashboard."""
    return InsightsOut(
        documents_by_type=documents_by_type(db),
        announcements_by_month=announcements_by_month(db),
        course_tags=course_tag_counts(db),
        course_semester_distribution=course_semester_distribution(db),
    )
