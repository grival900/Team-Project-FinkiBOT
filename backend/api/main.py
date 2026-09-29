import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.routers import admin, auth, chat, courses, documents, insights, mcp_tools, quiz, search, subscribe
from backend.core.config import get_settings
from backend.ingestion.embeddings import embed_texts
from backend.scheduler import start_scheduler

logger = logging.getLogger(__name__)
settings = get_settings()


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """Turns unhandled errors into a normal 500 response.

    Starlette's default error handler sits outside the CORS middleware, so its 500s
    have no CORS headers and the browser only shows "Failed to fetch". This one sits
    inside CORS, so the frontend can read the error."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # load the embedding model (~20s) now instead of on the first request
    embed_texts(["warmup"])

    # always created (paused if disabled) so the admin panel can turn it on later
    scheduler = start_scheduler(settings.scheduler_interval_minutes, settings.scheduler_slow_interval_minutes)
    if not settings.enable_scheduler:
        for job_id in ("scrape_and_notify", "scrape_slow"):
            scheduler.pause_job(job_id)
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="FinkiBOT API", version="0.1.0", lifespan=lifespan)

# must be added before CORSMiddleware so that CORS wraps it
app.add_middleware(UnhandledExceptionMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # lets the frontend read which model answered
    expose_headers=["X-LLM-Provider"],
)

app.include_router(search.router)
app.include_router(courses.router)
app.include_router(documents.router)
app.include_router(mcp_tools.router)
app.include_router(insights.router)
app.include_router(chat.router)
app.include_router(quiz.router)
app.include_router(subscribe.router)
app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
