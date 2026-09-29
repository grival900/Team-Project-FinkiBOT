"""Shared polite HTTP client for scrapers (official_site, finki_hub)."""

import time

import httpx

from backend.core.config import get_settings
from backend.core.site_settings import get_setting_cached

_last_request_at: float = 0.0


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": get_settings().scrape_user_agent},
        timeout=20.0,
        follow_redirects=True,
    )


def get(client: httpx.Client, url: str) -> httpx.Response:
    """GET with a delay between requests (set in the admin panel) to go easy on the site."""
    global _last_request_at
    delay = get_setting_cached("scrape_request_delay_seconds", get_settings().scrape_request_delay_seconds, float)
    elapsed = time.monotonic() - _last_request_at
    wait = delay - elapsed
    if wait > 0:
        time.sleep(wait)
    response = client.get(url)
    _last_request_at = time.monotonic()
    response.raise_for_status()
    return response
