from google.genai import types
from pydantic import BaseModel

from backend.api.schemas import QuizQuestion
from backend.core.config import get_settings
from backend.core.llm import get_client


class _QuizResult(BaseModel):
    questions: list[QuizQuestion]


def generate_quiz_from_text(
    content: str, num_questions: int, language_hint: str = "Macedonian", model: str | None = None
) -> list[QuizQuestion]:
    """Asks Gemini for multiple-choice questions. `response_schema` makes it return JSON
    that matches `_QuizResult`, so we don't have to parse free text."""
    client = get_client()

    prompt = (
        f"Based ONLY on the study material below, write {num_questions} multiple-choice "
        "quiz questions (exactly 4 options each, exactly one correct) to help a student "
        f"self-test. Write the questions in {language_hint}. Do not invent facts that "
        "aren't supported by the material.\n\nMaterial:\n" + content
    )

    response = client.models.generate_content(
        model=model or get_settings().llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_QuizResult,
        ),
    )

    result = response.parsed
    if not isinstance(result, _QuizResult):
        return []
    return result.questions
