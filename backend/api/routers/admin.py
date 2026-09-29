import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.api.schemas import (
    AdminUserPatch,
    ReindexStatusOut,
    ScraperEnabledOut,
    ScraperStatOut,
    SiteSettingsOut,
    SiteSettingsPatch,
    UserOut,
)
from backend.core.auth import require_admin
from backend.core.config import get_settings
from backend.core.llm_providers import GEMINI_MODELS, PROVIDERS
from backend.core.site_settings import (
    get_bool_setting,
    get_float_setting,
    get_int_or_none_setting,
    get_int_setting,
    get_str_setting,
    set_setting,
)
from backend.core.users import (
    LastAdminError,
    SelfActionError,
    count_other_active_admins,
    delete_user,
    guard_last_admin,
    guard_not_self,
    set_active_status,
    set_admin_status,
)
from backend.db import get_db
from backend.ingestion.pipeline import run_ingestion
from backend.models import User
from backend.notifier.emailer import send_password_reset_email
from backend.notifier.job import run_notification_job
from backend.scrapers.registry import SCRAPERS
from backend.scripts.export_seed import SEED_PATH, export_seed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@dataclass
class _ReindexJob:
    """State of the latest manual reindex, polled by the admin progress bar."""

    cadence: str
    scraper: str | None = None
    incremental: bool = False
    state: Literal["running", "done", "error"] = "running"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    progress_done: int = 0
    progress_total: int = 0
    current_scraper: str | None = None
    scrapers: list[ScraperStatOut] = field(default_factory=list)
    seed_refreshed: bool = False
    seed_document_count: int | None = None
    error: str | None = None


_reindex_lock = threading.Lock()
_reindex_job: _ReindexJob | None = None


def _background_reindex(
    cadence: str | None, refresh_seed: bool, incremental: bool = False, scraper: str | None = None
) -> None:
    global _reindex_job
    job = _ReindexJob(cadence=scraper or cadence or "full", scraper=scraper, incremental=incremental)
    with _reindex_lock:
        _reindex_job = job

    def on_progress(done: int, total: int, current: str | None) -> None:
        job.progress_done, job.progress_total, job.current_scraper = done, total, current

    try:
        stats = run_ingestion(cadence, progress_cb=on_progress, incremental=incremental, name=scraper)
    except Exception as exc:
        logger.exception("Background reindex failed")
        job.error = str(exc) or exc.__class__.__name__
        job.state = "error"
        job.finished_at = datetime.now(timezone.utc)
        return

    logger.info("Reindex (%s) finished: %s", scraper or cadence or "full", stats)
    job.scrapers = [
        ScraperStatOut(
            name=name, seen=s.seen, new=s.new, updated=s.updated, unchanged=s.unchanged, failed=s.failed
        )
        for name, s in stats.items()
    ]

    if not stats:
        # run_ingestion returns {} only when another ingestion already holds the lock.
        job.error = "Another indexing run was already in progress — nothing was done."
        job.state = "error"
        job.finished_at = datetime.now(timezone.utc)
        return

    if refresh_seed:
        try:
            job.seed_document_count = export_seed()
            job.seed_refreshed = True
            logger.info(
                "Refreshed bundled seed: %d documents written to %s", job.seed_document_count, SEED_PATH
            )
        except Exception:
            logger.exception("Reindex finished but refreshing the bundled seed failed")

    job.state = "done"
    job.finished_at = datetime.now(timezone.utc)


@router.post("/reindex")
def reindex(
    cadence: Literal["frequent", "slow"] | None = None,
    scraper: str | None = None,
    refresh_seed: bool = True,
    incremental: bool = False,
) -> dict[str, str]:
    """Starts a reindex in a background thread; poll /admin/reindex/status for progress.

    - `cadence`: "frequent", "slow", or empty for everything
    - `scraper`: run just one scraper by name
    - `incremental`: only fetch new URLs (misses edits to existing pages)
    - `refresh_seed`: rewrite backend/seed/documents.json.gz afterwards (commit it to share)
    """
    if scraper is not None and scraper not in {entry.name for entry in SCRAPERS}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown scraper name: {scraper!r}")
    with _reindex_lock:
        if _reindex_job is not None and _reindex_job.state == "running":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A reindex is already running")
    thread = threading.Thread(
        target=_background_reindex, args=(cadence, refresh_seed, incremental, scraper), daemon=True
    )
    thread.start()
    mode = "incremental" if incremental else "full scan"
    return {"status": f"reindex ({scraper or cadence or 'full'}, {mode}) started in background"}


@router.get("/reindex/status", response_model=ReindexStatusOut)
def reindex_status() -> ReindexStatusOut:
    """Progress + result of the most recent manual reindex. `state` is "idle" until one
    has been triggered since the last server start, then "running" → "done"/"error"."""
    job = _reindex_job
    if job is None:
        return ReindexStatusOut(state="idle")

    end = job.finished_at or datetime.now(timezone.utc)
    return ReindexStatusOut(
        state=job.state,
        cadence=job.cadence,
        incremental=job.incremental,
        started_at=job.started_at,
        finished_at=job.finished_at,
        duration_seconds=(end - job.started_at).total_seconds(),
        progress_done=job.progress_done,
        progress_total=job.progress_total,
        current_scraper=job.current_scraper,
        scrapers=job.scrapers,
        seed_refreshed=job.seed_refreshed,
        seed_document_count=job.seed_document_count,
        error=job.error,
    )


@router.post("/notify")
def notify() -> dict[str, int]:
    """Sends pending subscription emails now (the scheduler does this after each reindex)."""
    return {"notified": run_notification_job()}


# --- user management --------------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.created_at).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: UUID,
    payload: AdminUserPatch,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    will_demote = payload.is_admin is False and target.is_admin
    will_deactivate = payload.is_active is False and target.is_active
    if will_demote or will_deactivate:
        try:
            guard_not_self(target.id, current.id)
            guard_last_admin(target.is_admin and target.is_active, count_other_active_admins(db, target.id))
        except (SelfActionError, LastAdminError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if payload.is_admin is not None:
        set_admin_status(db, target, payload.is_admin)
    if payload.is_active is not None:
        set_active_status(db, target, payload.is_active)
    return target


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(user_id: UUID, db: Session = Depends(get_db), current: User = Depends(require_admin)) -> None:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        guard_not_self(target.id, current.id)
        guard_last_admin(target.is_admin and target.is_active, count_other_active_admins(db, target.id))
    except (SelfActionError, LastAdminError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    delete_user(db, target)


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.reset_token = secrets.token_urlsafe(32)
    target.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()

    reset_url = f"{get_settings().frontend_origin}/reset-password?token={target.reset_token}"
    send_password_reset_email(target.email, reset_url)
    return {"status": "reset_email_sent"}


# --- site settings -----------------------------------------------------------------


def _effective_settings(db: Session) -> SiteSettingsOut:
    defaults = get_settings()
    return SiteSettingsOut(
        scrape_announcement_limit=get_int_or_none_setting(
            db, "scrape_announcement_limit", defaults.scrape_announcement_limit
        ),
        scrape_subjects_limit=get_int_or_none_setting(db, "scrape_subjects_limit", defaults.scrape_subjects_limit),
        scrape_request_delay_seconds=get_float_setting(
            db, "scrape_request_delay_seconds", defaults.scrape_request_delay_seconds
        ),
        enable_scheduler=get_bool_setting(db, "enable_scheduler", defaults.enable_scheduler),
        scheduler_interval_minutes=get_int_setting(
            db, "scheduler_interval_minutes", defaults.scheduler_interval_minutes
        ),
        scheduler_slow_interval_minutes=get_int_setting(
            db, "scheduler_slow_interval_minutes", defaults.scheduler_slow_interval_minutes
        ),
        llm_provider=get_str_setting(db, "llm_provider", defaults.llm_provider),
        llm_model=get_str_setting(db, "llm_model", defaults.llm_model),
        scrapers=[
            ScraperEnabledOut(
                name=entry.name,
                enabled=entry.enabled and get_bool_setting(db, f"scraper_enabled:{entry.name}", True),
            )
            for entry in SCRAPERS
        ],
    )


@router.get("/settings", response_model=SiteSettingsOut)
def get_site_settings(db: Session = Depends(get_db)) -> SiteSettingsOut:
    return _effective_settings(db)


@router.put("/settings", response_model=SiteSettingsOut)
def update_site_settings(payload: SiteSettingsPatch, request: Request, db: Session = Depends(get_db)) -> SiteSettingsOut:
    fields = payload.model_fields_set  # distinguishes "sent as null" from "not sent" for the nullable ints
    scheduler = getattr(request.app.state, "scheduler", None)

    if "scrape_announcement_limit" in fields:
        set_setting(db, "scrape_announcement_limit", payload.scrape_announcement_limit)
    if "scrape_subjects_limit" in fields:
        set_setting(db, "scrape_subjects_limit", payload.scrape_subjects_limit)
    if payload.scrape_request_delay_seconds is not None:
        set_setting(db, "scrape_request_delay_seconds", payload.scrape_request_delay_seconds)

    if payload.enable_scheduler is not None and scheduler is not None:
        set_setting(db, "enable_scheduler", payload.enable_scheduler)
        for job_id in ("scrape_and_notify", "scrape_slow"):
            (scheduler.resume_job if payload.enable_scheduler else scheduler.pause_job)(job_id)

    if payload.scheduler_interval_minutes is not None:
        set_setting(db, "scheduler_interval_minutes", payload.scheduler_interval_minutes)
        if scheduler is not None:
            scheduler.reschedule_job("scrape_and_notify", trigger="interval", minutes=payload.scheduler_interval_minutes)
    if payload.scheduler_slow_interval_minutes is not None:
        set_setting(db, "scheduler_slow_interval_minutes", payload.scheduler_slow_interval_minutes)
        if scheduler is not None:
            scheduler.reschedule_job("scrape_slow", trigger="interval", minutes=payload.scheduler_slow_interval_minutes)

    if payload.llm_provider is not None:
        if payload.llm_provider not in PROVIDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown provider: {payload.llm_provider}")
        set_setting(db, "llm_provider", payload.llm_provider)
    if payload.llm_model is not None:
        # the form sends every field back, so also accept the .env model
        if payload.llm_model not in GEMINI_MODELS and payload.llm_model != get_settings().llm_model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown model: {payload.llm_model}")
        set_setting(db, "llm_model", payload.llm_model)

    if payload.scraper_enabled:
        valid_names = {entry.name for entry in SCRAPERS}
        for name, enabled in payload.scraper_enabled.items():
            if name not in valid_names:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown scraper: {name}")
            set_setting(db, f"scraper_enabled:{name}", enabled)

    return _effective_settings(db)
