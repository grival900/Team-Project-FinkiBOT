from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SearchResultOut(BaseModel):
    document_id: str
    title: str
    url: str
    source: str
    type: str
    published_at: datetime | None
    chunk_text: str
    score: float


class McpToolParam(BaseModel):
    name: str
    type: str
    required: bool
    default: str | int | None = None


class McpToolOut(BaseModel):
    server: str
    name: str
    description: str
    params: list[McpToolParam]


class McpCallRequest(BaseModel):
    server: str
    tool: str
    query: str
    limit: int = 5


class DocumentOut(BaseModel):
    id: str
    source: str
    type: str
    title: str
    url: str
    published_at: datetime | None
    content: str
    doc_metadata: dict


class DocTypeCount(BaseModel):
    source: str
    type: str
    count: int


class MonthCount(BaseModel):
    month: str
    count: int


class TagCount(BaseModel):
    tag: str
    count: int


class SemesterCount(BaseModel):
    semester: str
    count: int


class CourseCodeOption(BaseModel):
    code: str
    name: str


class InsightsOut(BaseModel):
    documents_by_type: list[DocTypeCount]
    announcements_by_month: list[MonthCount]
    course_tags: list[TagCount]
    course_semester_distribution: list[SemesterCount]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class SubscribeRequest(BaseModel):
    email: EmailStr
    keywords: list[str] = []
    course_codes: list[str] = []


class QuizQuestion(BaseModel):
    question: str
    choices: list[str]
    correct_index: int
    explanation: str


class QuizResponse(BaseModel):
    questions: list[QuizQuestion]
    source_titles: list[str]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # 72 bytes: bcrypt's own input cap


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AdminUserPatch(BaseModel):
    is_admin: bool | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class ScraperStatOut(BaseModel):
    name: str
    seen: int
    new: int
    updated: int
    unchanged: int
    failed: int


class ReindexStatusOut(BaseModel):
    state: Literal["idle", "running", "done", "error"]
    cadence: str | None = None
    incremental: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    progress_done: int = 0
    progress_total: int = 0
    current_scraper: str | None = None
    scrapers: list[ScraperStatOut] = []
    seed_refreshed: bool = False
    seed_document_count: int | None = None
    error: str | None = None


class ScraperEnabledOut(BaseModel):
    name: str
    enabled: bool


class SiteSettingsOut(BaseModel):
    scrape_announcement_limit: int | None
    scrape_subjects_limit: int | None
    scrape_request_delay_seconds: float
    enable_scheduler: bool
    scheduler_interval_minutes: int
    scheduler_slow_interval_minutes: int
    llm_provider: str
    llm_model: str
    scrapers: list[ScraperEnabledOut]


class SiteSettingsPatch(BaseModel):
    scrape_announcement_limit: int | None = None
    scrape_subjects_limit: int | None = None
    scrape_request_delay_seconds: float | None = None
    enable_scheduler: bool | None = None
    scheduler_interval_minutes: int | None = None
    scheduler_slow_interval_minutes: int | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    scraper_enabled: dict[str, bool] | None = None
