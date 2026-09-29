"""Settings the admin panel can change, stored in the `site_settings` table.

The .env value is the default; a row in this table overrides it. Secrets never go
here. Scrapers use `get_setting_cached`, which re-reads the table at most every 30s.
"""

import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.models import SiteSetting

T = TypeVar("T")

parse_int_or_none: Callable[[str], int | None] = lambda s: None if s == "" else int(s)  # noqa: E731
_parse_float: Callable[[str], float] = float
_parse_bool: Callable[[str], bool] = lambda s: s.lower() == "true"  # noqa: E731


def _serialize(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def get_setting(db: Session, key: str, default: T, parse: Callable[[str], T]) -> T:
    row = db.get(SiteSetting, key)
    if row is None:
        return default
    return parse(row.value)


def get_int_or_none_setting(db: Session, key: str, default: int | None) -> int | None:
    return get_setting(db, key, default, parse_int_or_none)


def get_int_setting(db: Session, key: str, default: int) -> int:
    return get_setting(db, key, default, int)


def get_float_setting(db: Session, key: str, default: float) -> float:
    return get_setting(db, key, default, _parse_float)


def get_bool_setting(db: Session, key: str, default: bool) -> bool:
    return get_setting(db, key, default, _parse_bool)


def get_str_setting(db: Session, key: str, default: str) -> str:
    return get_setting(db, key, default, str)


def set_setting(db: Session, key: str, value: object) -> None:
    row = db.get(SiteSetting, key)
    serialized = _serialize(value)
    if row is None:
        db.add(SiteSetting(key=key, value=serialized))
    else:
        row.value = serialized
    db.commit()
    _cache_invalidate()


# --- cached, session-free access for scraper code -------------------------------

_cache: dict[str, str] | None = None
_cache_loaded_at: float = 0.0
_CACHE_TTL_SECONDS = 30.0


def _cache_invalidate() -> None:
    global _cache
    _cache = None


def _load_cache() -> dict[str, str]:
    global _cache, _cache_loaded_at
    now = time.monotonic()
    if _cache is not None and (now - _cache_loaded_at) < _CACHE_TTL_SECONDS:
        return _cache
    with SessionLocal() as db:
        rows = db.query(SiteSetting).all()
    _cache = {row.key: row.value for row in rows}
    _cache_loaded_at = now
    return _cache


def get_setting_cached(key: str, default: T, parse: Callable[[str], T]) -> T:
    raw = _load_cache().get(key)
    if raw is None:
        return default
    return parse(raw)
