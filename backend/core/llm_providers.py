"""Gemini and Groq behind one interface, so /chat can switch to the other one when
the first is out of quota.

Gemini's SDK runs the tool-calling loop for us. Groq's doesn't, so `stream_groq` does
it by hand with the same tool functions. Groq answers arrive in one piece instead of
streaming - fine for a fallback.

Groq's free tier allows only 8000 tokens per minute, and every tool round re-sends the
whole conversation. So Groq gets the question without the retrieved context and has to
look things up with a tool call first - that keeps a normal answer under the limit.
"""

import inspect
import json
import logging
import time
import typing
from collections.abc import Callable, Iterator
from typing import Any

import httpx
from google.genai import errors as genai_errors
from google.genai import types
from groq import APIConnectionError as GroqAPIConnectionError
from groq import APIStatusError as GroqAPIStatusError
from groq import AuthenticationError as GroqAuthenticationError

from backend.core.config import get_settings
from backend.core.llm import get_client, get_groq_client

logger = logging.getLogger(__name__)

PROVIDERS = ("gemini", "groq")

# Models selectable in the admin panel. Each has its own free-tier quota.
GEMINI_MODELS = ("gemini-2.5-flash", "gemini-3.1-flash-lite")
# Upper limit on tool calls per answer, so a confused model can't loop forever.
MAX_TOOL_CALLS = 8
_MAX_TOOL_CALLS_EXCEEDED_MESSAGE = (
    "Извинете, прашањето бараше премногу чекори за да го обработам целосно - "
    "обидете се да го поедноставите или поставете го повторно."
)
_BOTH_PROVIDERS_UNAVAILABLE_MESSAGE = (
    "Извинете, моментално не можам да одговорам - и двата модели (Gemini и Groq) се "
    "недостапни во моментов. Обидете се повторно наскоро."
)

# Errors worth retrying on the other provider: 429 quota, 503 overloaded, and 413,
# which is how Groq reports hitting its tokens-per-minute limit.
_RETRYABLE_STATUS_CODES = {429, 503, 413}
# If Groq hits its per-minute limit in the middle of a tool chain, wait this long at most
# and try the round again, instead of throwing away the work already done.
GROQ_MAX_RATE_LIMIT_WAIT_SECONDS = 20


class QuotaExceededError(Exception):
    """The provider can't answer right now (quota, overload, network) - try the other one."""


def _fallback_provider(preferred: str) -> str:
    return "groq" if preferred == "gemini" else "gemini"


def _to_gemini_contents(messages: list[dict[str, str]]) -> list[types.Content]:
    return [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in messages
    ]


def _thinking_config(model: str) -> types.ThinkingConfig | None:
    """2.5 models take a thinking budget (-1 = let the model decide), Gemini 3 takes a
    level instead. The Lite models default to minimal thinking, which was too little
    to use the tools properly, so we ask for medium."""
    if model.startswith("gemini-2.5"):
        return types.ThinkingConfig(thinking_budget=-1)
    if model.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.MEDIUM)
    return None


def stream_gemini(
    messages: list[dict[str, str]], tools: list[Callable], system_prompt: str, model: str | None = None
) -> Iterator[str]:
    model = model or get_settings().llm_model
    client = get_client()
    try:
        stream = client.models.generate_content_stream(
            model=model,
            contents=_to_gemini_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=4096,
                temperature=0.2,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=MAX_TOOL_CALLS),
                thinking_config=_thinking_config(model),
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
    except genai_errors.APIError as e:
        if e.code in _RETRYABLE_STATUS_CODES:
            raise QuotaExceededError(str(e)) from e
        raise
    except httpx.TransportError as e:
        # network error (DNS, timeout...) - also worth trying the other provider
        raise QuotaExceededError(str(e)) from e


def _python_type_to_json_type(py_type: type) -> str:
    return {str: "string", int: "integer", float: "number", bool: "boolean"}.get(py_type, "string")


def _groq_tool_schema(fn: Callable) -> dict[str, Any]:
    """OpenAI-style tool schema from a function's signature and docstring (Gemini's
    SDK does this for us). Only handles str/int/float/bool, which is all we use.
    Optional parameters also accept null - Groq's models send null for arguments they
    skip, and Groq rejects the whole call if the schema doesn't allow it."""
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        json_type = _python_type_to_json_type(hints.get(name, str))
        if param.default is inspect.Parameter.empty:
            properties[name] = {"type": json_type}
            required.append(name)
        else:
            properties[name] = {"type": [json_type, "null"]}
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip(),
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def _execute_groq_tool_call(function_map: dict[str, Callable], tool_call: Any) -> dict[str, Any]:
    fn = function_map.get(tool_call.function.name)
    if fn is None:
        return {"error": f"unknown tool {tool_call.function.name!r}"}
    try:
        kwargs = json.loads(tool_call.function.arguments or "{}")
        # null means "not given" - let the function use its default
        return {"result": fn(**{k: v for k, v in kwargs.items() if v is not None})}
    except Exception as e:
        logger.warning("Groq tool call %s failed: %s", tool_call.function.name, e)
        return {"error": str(e)}


def stream_groq(messages: list[dict[str, str]], tools: list[Callable], system_prompt: str) -> Iterator[str]:
    settings = get_settings()
    client = get_groq_client()
    function_map = {fn.__name__: fn for fn in tools}
    tool_schemas = [_groq_tool_schema(fn) for fn in tools]
    convo: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}, *messages]

    try:
        for round_number in range(MAX_TOOL_CALLS):
            response = _groq_round(
                client,
                model=settings.groq_model,
                messages=convo,
                tools=tool_schemas,
                # the first round must look something up - Groq doesn't get the context
                tool_choice="required" if round_number == 0 and tools else "auto",
                can_wait=round_number > 0,
            )
            message = response.choices[0].message
            tool_calls = message.tool_calls or []
            if not tool_calls:
                yield message.content or ""
                return

            convo.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                result = _execute_groq_tool_call(function_map, tc)
                convo.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False)})
        yield _MAX_TOOL_CALLS_EXCEEDED_MESSAGE
    except (GroqAPIConnectionError, GroqAuthenticationError) as e:
        # no network or no/invalid GROQ_API_KEY - Groq isn't usable right now
        raise QuotaExceededError(str(e)) from e
    except GroqAPIStatusError as e:
        # checked by status code because Groq's token limit comes back as 413, not 429
        if e.status_code in _RETRYABLE_STATUS_CODES:
            raise QuotaExceededError(str(e)) from e
        raise


def _groq_round(client: Any, can_wait: bool, **request: Any) -> Any:
    """One Groq request. After the first round, a rate-limit error is retried once
    after the wait Groq asks for (if it's short enough)."""
    try:
        return client.chat.completions.create(**request)
    except GroqAPIStatusError as e:
        wait = _retry_after_seconds(e)
        if not can_wait or e.status_code not in (429, 413) or wait is None or wait > GROQ_MAX_RATE_LIMIT_WAIT_SECONDS:
            raise
        logger.info("Groq rate limit mid-answer, waiting %.1fs", wait)
        time.sleep(wait)
        return client.chat.completions.create(**request)


def _retry_after_seconds(error: GroqAPIStatusError) -> float | None:
    try:
        return float(error.response.headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


_STREAMERS: dict[str, Callable[..., Iterator[str]]] = {
    "gemini": stream_gemini,
    "groq": stream_groq,
}


def stream_chat_with_failover(
    preferred: str,
    messages: list[dict[str, str]],
    tools: list[Callable],
    system_prompt: str,
    gemini_model: str | None = None,
    groq_messages: list[dict[str, str]] | None = None,
) -> tuple[str, Iterator[str]]:
    """Tries `preferred`, and the other provider if the first one fails before
    answering. Returns (provider_used, chunks).

    We pull the first chunk here so we already know which provider answered (it goes
    in a response header). A failure halfway through an answer can't be retried. If
    both fail, the chunks are just an apology message.

    `groq_messages` is a smaller version of `messages` for Groq (without the context)."""
    provider = preferred if preferred in PROVIDERS else "gemini"
    fallback = _fallback_provider(provider)

    def start(name: str) -> Iterator[str]:
        if name == "groq":
            return _STREAMERS[name](groq_messages or messages, tools, system_prompt)
        extra = {"model": gemini_model} if gemini_model else {}
        return _STREAMERS[name](messages, tools, system_prompt, **extra)

    try:
        stream = start(provider)
        first = next(stream, "")
        return provider, _prepend(first, stream)
    except QuotaExceededError:
        logger.warning("%s is unavailable (quota/rate-limit/connection), falling back to %s", provider, fallback)

    try:
        stream = start(fallback)
        first = next(stream, "")
        return fallback, _prepend(first, stream)
    except QuotaExceededError:
        logger.error("%s is also unavailable - no provider could serve this request", fallback)
        return provider, iter([_BOTH_PROVIDERS_UNAVAILABLE_MESSAGE])


def _prepend(first: str, rest: Iterator[str]) -> Iterator[str]:
    if first:
        yield first
    yield from rest
