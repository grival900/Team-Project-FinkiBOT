from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.api.schemas import QuizResponse
from backend.core.config import get_settings
from backend.core.site_settings import get_str_setting
from backend.db import get_db
from backend.quiz.extraction import extract_text
from backend.quiz.generation import generate_quiz_from_text

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/upload", response_model=QuizResponse)
async def upload(
    file: UploadFile = File(...), num_questions: int = Form(5), db: Session = Depends(get_db)
) -> QuizResponse:
    """Makes a quiz from an uploaded PDF/PPTX. The file isn't saved anywhere."""
    data = await file.read()
    try:
        text = extract_text(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the uploaded file")

    model = get_str_setting(db, "llm_model", get_settings().llm_model)
    questions = generate_quiz_from_text(text, num_questions, model=model)
    return QuizResponse(questions=questions, source_titles=[file.filename or "uploaded file"])
