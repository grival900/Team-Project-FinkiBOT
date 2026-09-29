"""MCP server exposing a *live* search over finki.ukim.mk's WordPress content, via the
site's own public REST API (`wp-json/wp/v2/search`) — unlike `official_mcp`/
`finki_hub_mcp`, this never touches the local index, so it can surface things before
the next reindex, at the cost of one live HTTP round trip per call.

Not built on a "finished" third-party WordPress MCP server: the obvious credential-free
candidate (`wppoland/woocommerce-mcp`'s `search_posts`) queries `wp/v2/posts`, which
returns zero results on finki.ukim.mk — its real content lives entirely in custom post
types (`schedule`, `announcement`, etc.) that endpoint never looks at. `wp/v2/search`
is the one confirmed (live) to actually find them, and needs no authentication.

Run standalone: `python -m backend.mcp_servers.official_live_mcp.server`
"""

import logging

import httpx
from mcp.server.fastmcp import FastMCP

from backend.scrapers.http import make_client
from backend.scrapers.official_site.base import BASE_URL

logger = logging.getLogger(__name__)

mcp = FastMCP("finki-official-live")

SEARCH_PATH = "/wp-json/wp/v2/search"
# A single small JSON call triggered by one user query — generous enough for a slow
# response, short enough not to stall a chat reply.
REQUEST_TIMEOUT_SECONDS = 10.0


def parse_wp_search_response(results: list[dict]) -> list[dict]:
    """Pure parsing step, unit-testable against a saved fixture. `wp/v2/search` returns
    more fields than this (subtype-specific `_links`, `type`), but title/url/type/
    subtype is what a caller needs to know what a hit is and where to look."""
    return [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "type": r.get("type"),
            "subtype": r.get("subtype"),
        }
        for r in results
    ]


@mcp.tool()
def search_official_site_live(query: str, limit: int = 5) -> list[dict]:
    """Live search across finki.ukim.mk's WordPress content (announcements,
    exam-session postings, static pages, and any other custom post type the site
    uses) via the site's own search endpoint - not the locally indexed copy, so it can
    surface things before the next reindex. Returns title/url/type only (no excerpt),
    since fetching each hit's full content would mean an extra live request per hit."""
    try:
        with make_client() as client:
            response = client.get(
                f"{BASE_URL}{SEARCH_PATH}",
                params={"search": query, "per_page": limit},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            results = response.json()
    except httpx.HTTPError:
        logger.exception("Live WordPress search failed for query: %s", query)
        return []

    return parse_wp_search_response(results)


if __name__ == "__main__":
    mcp.run()
