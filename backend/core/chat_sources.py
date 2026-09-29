"""Everything about sources in a chat answer: the context block the model reads, and
the single "Извори" link appended after the answer."""

import math
import re
from urllib.parse import urlparse

from backend.core.config import get_settings
from backend.core.retrieval import SearchResult

settings = get_settings()

_TYPE_LABEL = {
    "course": "предмет",
    "professor": "професор",
    "staff": "наставник",
    "announcement": "објава",
    "material": "материјали",
    "schedule": "распоред",
    "page": "страница",
    "event": "настан",
    "project": "проект",
    "job": "оглас за работа/пракса",
    "thesis": "дипломска/магистерска",
    "document": "документ",
}
_FRONTEND_HOST = urlparse(settings.frontend_origin).netloc.removeprefix("www.")


def citation_url(result: SearchResult) -> str:
    """finki-hub course pages have no per-course URL, so link the official syllabus
    if we know it, otherwise our own document page. Theses link to their PDF if any."""
    if result.source == "finki_hub" and result.type == "course":
        return result.metadata.get("official_subject_url") or f"{settings.frontend_origin}/documents/{result.document_id}"
    if result.type == "thesis":
        return result.metadata.get("pdf_url") or result.url
    return result.url


def _display_host(url: str) -> str:
    host = urlparse(url).netloc.removeprefix("www.")
    if host == _FRONTEND_HOST or host.endswith("finki-hub.com"):
        return "finki-hub.com"
    if host.endswith("finki.ukim.mk"):
        return "finki.ukim.mk"
    return host or "врска"


def source_label(result: SearchResult) -> str:
    """e.g. "Оперативни системи (предмет, finki.ukim.mk)"."""
    kind = _TYPE_LABEL.get(result.type, result.type)
    return f"{result.title} ({kind}, {_display_host(citation_url(result))})"


def live_results_to_search_results(items: list[dict]) -> list[SearchResult]:
    """Wraps live site-search hits (title + url only) so they fit the same pipeline."""
    return [
        SearchResult(
            document_id=f"live:{item['url']}",
            title=item.get("title") or item["url"],
            url=item["url"],
            source="official",
            type=item.get("subtype") or item.get("type") or "page",
            published_at=None,
            chunk_text="(live search result — title and link only, page content not fetched)",
            score=0.0,
            metadata={"live": True},
        )
        for item in items
        if item.get("url")
    ]


def build_context(results: list[SearchResult]) -> str:
    if not results:
        return "(no matching context found)"
    blocks = []
    for r in results:
        date = r.published_at.date().isoformat() if r.published_at else "n/a"
        blocks.append(f"[{r.title}] (type: {r.type}, url: {citation_url(r)}, date: {date})\n{r.chunk_text}")
    return "\n\n---\n\n".join(blocks)


# --- picking the one source to cite -----------------------------------------------

# Words, plus numbers like dates/times/rooms ("10.09.2026", "11:30", "117").
_TOKEN_RE = re.compile(r"\d+(?:[.:/]\d+)*|[^\W\d_]+")
# Need at least this many distinctive words/numbers in common with the answer before
# we'll cite a document at all - otherwise the answer probably didn't come from it.
MIN_SHARED_TOKENS = 2


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 3 or (t[0].isdigit() and len(t) >= 2)}


def pick_source(answer: str, results: list[SearchResult]) -> SearchResult | None:
    """Picks the document the answer was most likely built from.

    Retrieval score only says how close a document was to the *question*. What we want
    is the one the *answer* quotes, so each document is scored by the words and numbers
    it shares with the answer. Rare tokens count more (weighted like IDF): a date or a
    room number that only one document contains says a lot, a word like "испит" that
    every candidate contains says almost nothing. Ties go to the higher retrieval score.
    """
    docs: dict[str, tuple[SearchResult, set[str]]] = {}
    for r in results:
        key = citation_url(r)  # the finki-hub and official copy of a course can share a link
        best, tokens = docs.get(key, (r, set()))
        if r.score > best.score:
            best = r
        docs[key] = (best, tokens | _tokens(r.title) | _tokens(r.chunk_text))
    if not docs:
        return None

    answer_tokens = _tokens(answer)
    doc_freq: dict[str, int] = {}
    for _, tokens in docs.values():
        for t in tokens & answer_tokens:
            doc_freq[t] = doc_freq.get(t, 0) + 1

    n = len(docs)
    best_result, best_key = None, (0.0, 0.0)
    for result, tokens in docs.values():
        shared = tokens & answer_tokens
        # a token every candidate has doesn't help tell them apart (unless there's only one)
        distinctive = [t for t in shared if doc_freq[t] < n or n == 1]
        if len(distinctive) < MIN_SHARED_TOKENS:
            continue
        overlap = sum(math.log((n + 1) / doc_freq[t]) for t in shared)
        if (overlap, result.score) > best_key:
            best_result, best_key = result, (overlap, result.score)
    return best_result


def build_sources_block(source: SearchResult | None) -> str:
    if source is None:
        return ""
    return f"\n\n---\n\n**Извори:**\n- [{source_label(source)}]({citation_url(source)})"


# --- removing a source list the model wrote itself ---------------------------------

# The prompt says not to, but the model sometimes ends with its own "Извори:" list
# anyway. We cut from that heading on and append ours instead.
_SOURCES_HEADING_RE = re.compile(
    r"\n\s*(?:[-*_]{3,}\s*)?"  # optional --- rule
    r"(?:\*{1,2}|__|#{1,6}[ \t]*)?"  # optional bold / heading markup
    r"(?:извори|sources|референци|references)"
    r"[ \t]*:?[ \t]*(?:\*{1,2}|__)?[ \t]*\n",
    re.IGNORECASE,
)
# While streaming, hold back this many characters so a half-arrived heading isn't sent.
HEADING_LOOKBACK = 64


def model_sources_start(text: str) -> int | None:
    """Index where a model-written source list starts, or None."""
    m = _SOURCES_HEADING_RE.search(text)
    return m.start() if m else None
