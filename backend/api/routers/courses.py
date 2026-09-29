from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.schemas import CourseCodeOption
from backend.core.insights import course_code_options
from backend.db import get_db

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/codes", response_model=list[CourseCodeOption])
def get_course_codes(db: Session = Depends(get_db)) -> list[CourseCodeOption]:
    """Backs the course-code picker on the Notifications page — one entry per
    finki_hub course that has an accreditation code (see `build_course_code_options`)."""
    return [CourseCodeOption(**o) for o in course_code_options(db)]
