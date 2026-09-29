from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.schemas import ChatRequest
from backend.core.chat_prompt import SYSTEM_PROMPT
from backend.core.chat_ranking import prefer_current_year
from backend.core.chat_sources import (
    HEADING_LOOKBACK,
    build_context,
    build_sources_block,
    live_results_to_search_results,
    model_sources_start,
    pick_source,
)
from backend.core.chat_tools import build_chat_tools
from backend.core.config import get_settings
from backend.core.llm_providers import stream_chat_with_failover
from backend.core.retrieval import SearchResult, search
from backend.core.site_settings import get_float_setting, get_str_setting
from backend.db import get_db
from backend.mcp_servers.official_live_mcp.server import search_official_site_live

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()

# Pull a wide pool so a current-year match has a chance to show up next to the older
# copies of the same text, then keep the best few after re-ranking.
CANDIDATE_POOL_K = 24
CHAT_RESULT_K = 6
# Only used when the local index has nothing for the question.
LIVE_FALLBACK_LIMIT = 3


def strip_model_sources(chunks: Iterator[str]) -> Iterator[str]:
    """Streams the answer through, cutting off any source list the model wrote itself."""
    acc = ""
    sent = 0
    for chunk_text in chunks:
        acc += chunk_text or ""
        cut = model_sources_start(acc)
        if cut is not None:
            if cut > sent:
                yield acc[sent:cut]
            for _ in chunks:  # drain the rest
                pass
            return
        safe = len(acc) - HEADING_LOOKBACK
        if safe > sent:
            yield acc[sent:safe]
            sent = safe
    yield acc[sent:].rstrip()


@router.post("")
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    now = datetime.now(timezone.utc)
    min_score = get_float_setting(db, "chat_min_score", settings.chat_min_score)

    candidates = search(db, payload.message, k=CANDIDATE_POOL_K, min_score=min_score)
    results = prefer_current_year(candidates, k=CHAT_RESULT_K, current_year=now.year, now=now)
    if not results:
        results = live_results_to_search_results(search_official_site_live(payload.message, limit=LIVE_FALLBACK_LIMIT))

    # the tools append whatever they find here, so it can be cited at the end
    tool_results: list[SearchResult] = []
    tools = build_chat_tools(db, min_score, tool_results)

    history = [{"role": m.role, "content": m.content} for m in payload.history]
    today = f"Today's date: {now.date().isoformat()}"
    messages = history + [
        {"role": "user", "content": f"{today}\n\nContext:\n{build_context(results)}\n\nQuestion: {payload.message}"}
    ]
    # Groq's token limit is too small for the context; it uses the tools instead
    groq_messages = history + [{"role": "user", "content": f"{today}\n\nQuestion: {payload.message}"}]

    preferred = get_str_setting(db, "llm_provider", settings.llm_provider)
    gemini_model = get_str_setting(db, "llm_model", settings.llm_model)
    # Starts the stream before responding, so we can fall back to the other provider
    # and still know which one answered for the X-LLM-Provider header.
    provider_used, chunks = stream_chat_with_failover(
        preferred, messages, tools, SYSTEM_PROMPT, gemini_model, groq_messages=groq_messages
    )

    def event_stream() -> Iterator[str]:
        answer = ""
        for part in strip_model_sources(chunks):
            answer += part
            yield part
        yield build_sources_block(pick_source(answer, results + tool_results))

    return StreamingResponse(event_stream(), media_type="text/plain", headers={"X-LLM-Provider": provider_used})
