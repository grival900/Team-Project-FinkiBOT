from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors
from groq import InternalServerError as GroqInternalServerError
from groq import RateLimitError as GroqRateLimitError

from backend.core import llm_providers
from backend.core.llm_providers import (
    QuotaExceededError,
    _execute_groq_tool_call,
    _fallback_provider,
    _groq_tool_schema,
    _thinking_config,
    stream_chat_with_failover,
)


def _http_error(status_code: int):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    response.json.return_value = {"error": {"message": "boom"}}
    return response


def test_fallback_provider_swaps_gemini_and_groq():
    assert _fallback_provider("gemini") == "groq"
    assert _fallback_provider("groq") == "gemini"


def test_thinking_config_uses_dynamic_budget_for_the_2_5_family():
    for model in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
        assert _thinking_config(model).thinking_budget == -1


def test_thinking_config_uses_medium_level_for_the_gemini_3_family():
    for model in ("gemini-3.1-flash-lite", "gemini-3.5-flash"):
        config = _thinking_config(model)
        assert config.thinking_level == "MEDIUM"
        assert config.thinking_budget is None


def test_thinking_config_is_omitted_for_models_without_thinking():
    assert _thinking_config("gemini-2.0-flash") is None


def test_groq_tool_schema_reflects_signature_and_docstring():
    def search_courses(query: str, limit: int = 5) -> list[dict]:
        """Search FINKI courses by name or topic."""
        return []

    schema = _groq_tool_schema(search_courses)

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "search_courses"
    assert schema["function"]["description"] == "Search FINKI courses by name or topic."
    assert schema["function"]["parameters"]["properties"] == {
        "query": {"type": "string"},
        "limit": {"type": ["integer", "null"]},
    }
    # only `query` has no default, so only it is required
    assert schema["function"]["parameters"]["required"] == ["query"]


def test_execute_groq_tool_call_invokes_the_matching_function():
    def echo(text: str) -> dict:
        return {"echo": text}

    tool_call = MagicMock()
    tool_call.function.name = "echo"
    tool_call.function.arguments = '{"text": "hi"}'

    result = _execute_groq_tool_call({"echo": echo}, tool_call)

    assert result == {"result": {"echo": "hi"}}


def test_execute_groq_tool_call_reports_an_unknown_tool_without_raising():
    tool_call = MagicMock()
    tool_call.function.name = "does_not_exist"

    result = _execute_groq_tool_call({}, tool_call)

    assert result == {"error": "unknown tool 'does_not_exist'"}


def test_execute_groq_tool_call_wraps_a_failing_tool_as_an_error_not_an_exception():
    def boom(**kwargs):
        raise ValueError("bad args")

    tool_call = MagicMock()
    tool_call.function.name = "boom"
    tool_call.function.arguments = "{}"

    result = _execute_groq_tool_call({"boom": boom}, tool_call)

    assert result == {"error": "bad args"}


def test_stream_chat_with_failover_uses_the_preferred_provider_when_it_succeeds():
    with patch.object(llm_providers, "_STREAMERS", {"gemini": lambda *a: iter(["hi"]), "groq": lambda *a: iter(["nope"])}):
        provider, chunks = stream_chat_with_failover("gemini", [], [], "system")

    assert provider == "gemini"
    assert list(chunks) == ["hi"]


def test_stream_chat_with_failover_passes_the_gemini_model_only_to_gemini():
    seen: dict[str, dict] = {}

    def gemini(*a, **kw):
        seen["gemini"] = kw
        raise QuotaExceededError("429")

    def groq(*a, **kw):
        seen["groq"] = kw
        return iter(["from groq"])

    with patch.object(llm_providers, "_STREAMERS", {"gemini": gemini, "groq": groq}):
        provider, _ = stream_chat_with_failover("gemini", [], [], "system", gemini_model="gemini-3.1-flash-lite")

    assert provider == "groq"
    assert seen == {"gemini": {"model": "gemini-3.1-flash-lite"}, "groq": {}}


def test_stream_chat_with_failover_falls_back_on_quota_exceeded():
    def failing(*_a):
        raise QuotaExceededError("rate limited")
        yield  # pragma: no cover - makes this a generator function

    with patch.object(llm_providers, "_STREAMERS", {"gemini": failing, "groq": lambda *a: iter(["from groq"])}):
        provider, chunks = stream_chat_with_failover("gemini", [], [], "system")

    assert provider == "groq"
    assert list(chunks) == ["from groq"]


def test_stream_chat_with_failover_returns_an_apology_when_both_providers_fail():
    def failing(*_a):
        raise QuotaExceededError("down")
        yield  # pragma: no cover - makes this a generator function

    with patch.object(llm_providers, "_STREAMERS", {"gemini": failing, "groq": failing}):
        provider, chunks = stream_chat_with_failover("gemini", [], [], "system")

    assert provider == "gemini"
    assert list(chunks) == [llm_providers._BOTH_PROVIDERS_UNAVAILABLE_MESSAGE]


def test_stream_chat_with_failover_unknown_provider_defaults_to_gemini():
    with patch.object(llm_providers, "_STREAMERS", {"gemini": lambda *a: iter(["hi"]), "groq": lambda *a: iter(["nope"])}):
        provider, chunks = stream_chat_with_failover("not-a-real-provider", [], [], "system")

    assert provider == "gemini"
    assert list(chunks) == ["hi"]


def test_stream_gemini_raises_quota_exceeded_on_429():
    client = MagicMock()
    client.models.generate_content_stream.side_effect = genai_errors.ClientError(429, {"error": {"message": "quota"}})

    with patch.object(llm_providers, "get_client", return_value=client):
        stream = llm_providers.stream_gemini([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(QuotaExceededError):
            next(stream)


def test_stream_gemini_reraises_a_non_retryable_error():
    client = MagicMock()
    client.models.generate_content_stream.side_effect = genai_errors.ClientError(400, {"error": {"message": "bad"}})

    with patch.object(llm_providers, "get_client", return_value=client):
        stream = llm_providers.stream_gemini([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(genai_errors.ClientError):
            next(stream)


def test_stream_gemini_raises_quota_exceeded_on_a_network_failure():
    """A DNS/connection failure never gets far enough to have an HTTP status at all -
    still means "this provider isn't reachable right now", same as a 429/503."""
    import httpx

    client = MagicMock()
    client.models.generate_content_stream.side_effect = httpx.ConnectError("connection refused")

    with patch.object(llm_providers, "get_client", return_value=client):
        stream = llm_providers.stream_gemini([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(QuotaExceededError):
            next(stream)


def test_stream_groq_raises_quota_exceeded_on_missing_or_invalid_api_key():
    from groq import AuthenticationError as GroqAuthenticationError

    client = MagicMock()
    client.chat.completions.create.side_effect = GroqAuthenticationError(
        message="invalid api key", response=_http_error(401), body=None
    )

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        stream = llm_providers.stream_groq([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(QuotaExceededError):
            next(stream)


def test_stream_groq_raises_quota_exceeded_on_rate_limit():
    client = MagicMock()
    client.chat.completions.create.side_effect = GroqRateLimitError(
        message="rate limited", response=_http_error(429), body=None
    )

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        stream = llm_providers.stream_groq([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(QuotaExceededError):
            next(stream)


def test_stream_groq_raises_quota_exceeded_on_internal_server_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = GroqInternalServerError(
        message="overloaded", response=_http_error(503), body=None
    )

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        stream = llm_providers.stream_groq([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(QuotaExceededError):
            next(stream)


def test_stream_groq_raises_quota_exceeded_on_413_token_rate_limit():
    # Groq reports its tokens-per-minute limit as 413, not 429
    from groq import APIStatusError as GroqAPIStatusError

    client = MagicMock()
    client.chat.completions.create.side_effect = GroqAPIStatusError(
        message="Request too large", response=_http_error(413), body=None
    )

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        stream = llm_providers.stream_groq([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(QuotaExceededError):
            next(stream)


def test_stream_groq_reraises_a_non_retryable_status_error():
    from groq import APIStatusError as GroqAPIStatusError

    client = MagicMock()
    client.chat.completions.create.side_effect = GroqAPIStatusError(
        message="bad request", response=_http_error(400), body=None
    )

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        stream = llm_providers.stream_groq([{"role": "user", "content": "hi"}], [], "system")
        with pytest.raises(GroqAPIStatusError):
            next(stream)


def test_stream_groq_yields_the_final_answer_once_no_tool_calls_remain():
    client = MagicMock()
    final_response = MagicMock()
    final_response.choices[0].message.tool_calls = None
    final_response.choices[0].message.content = "the answer"
    client.chat.completions.create.return_value = final_response

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        chunks = list(llm_providers.stream_groq([{"role": "user", "content": "hi"}], [], "system"))

    assert chunks == ["the answer"]


def test_stream_groq_executes_a_tool_call_then_answers():
    def get_thing(name: str) -> dict:
        return {"name": name}

    client = MagicMock()

    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "get_thing"
    tool_call.function.arguments = '{"name": "x"}'

    round_1 = MagicMock()
    round_1.choices[0].message.tool_calls = [tool_call]
    round_1.choices[0].message.content = None

    round_2 = MagicMock()
    round_2.choices[0].message.tool_calls = None
    round_2.choices[0].message.content = "resolved: x"

    client.chat.completions.create.side_effect = [round_1, round_2]

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        chunks = list(llm_providers.stream_groq([{"role": "user", "content": "hi"}], [get_thing], "system"))

    assert chunks == ["resolved: x"]
    assert client.chat.completions.create.call_count == 2
    # the tool result must have been fed back into the second round's messages
    second_call_messages = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_messages = [m for m in second_call_messages if m["role"] == "tool"]
    assert len(tool_messages) == 1
    assert "x" in tool_messages[0]["content"]


def _tool_round(name: str = "get_thing", arguments: str = '{"name": "x"}') -> MagicMock:
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = name
    tool_call.function.arguments = arguments
    response = MagicMock()
    response.choices[0].message.tool_calls = [tool_call]
    response.choices[0].message.content = None
    return response


def _answer_round(text: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.tool_calls = None
    response.choices[0].message.content = text
    return response


def test_stream_groq_requires_a_tool_call_in_the_first_round_only():
    def get_thing(name: str) -> dict:
        return {"name": name}

    client = MagicMock()
    client.chat.completions.create.side_effect = [_tool_round(), _answer_round("done")]

    with patch.object(llm_providers, "get_groq_client", return_value=client):
        list(llm_providers.stream_groq([{"role": "user", "content": "hi"}], [get_thing], "system"))

    choices = [c.kwargs["tool_choice"] for c in client.chat.completions.create.call_args_list]
    assert choices == ["required", "auto"]


def test_stream_groq_waits_and_retries_when_the_token_limit_hits_mid_chain():
    from groq import APIStatusError as GroqAPIStatusError

    def get_thing(name: str) -> dict:
        return {"name": name}

    rate_limited = _http_error(429)
    rate_limited.headers = {"retry-after": "2.5"}
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _tool_round(),
        GroqAPIStatusError(message="rate limit", response=rate_limited, body=None),
        _answer_round("after waiting"),
    ]

    with (
        patch.object(llm_providers, "get_groq_client", return_value=client),
        patch.object(llm_providers.time, "sleep") as sleep,
    ):
        chunks = list(llm_providers.stream_groq([{"role": "user", "content": "hi"}], [get_thing], "system"))

    assert chunks == ["after waiting"]
    sleep.assert_called_once_with(2.5)


def test_stream_groq_does_not_wait_on_a_rate_limit_in_the_first_round():
    # nothing is lost yet, so falling back to Gemini is faster than waiting
    from groq import APIStatusError as GroqAPIStatusError

    rate_limited = _http_error(429)
    rate_limited.headers = {"retry-after": "2.5"}
    client = MagicMock()
    client.chat.completions.create.side_effect = GroqAPIStatusError(message="rate limit", response=rate_limited, body=None)

    with (
        patch.object(llm_providers, "get_groq_client", return_value=client),
        patch.object(llm_providers.time, "sleep") as sleep,
    ):
        with pytest.raises(QuotaExceededError):
            next(llm_providers.stream_groq([{"role": "user", "content": "hi"}], [], "system"))

    sleep.assert_not_called()


def test_stream_chat_with_failover_gives_groq_its_own_messages():
    seen = {}

    def groq(messages, *a, **kw):
        seen["groq"] = messages
        return iter(["ok"])

    with patch.object(llm_providers, "_STREAMERS", {"gemini": lambda *a, **kw: iter(["x"]), "groq": groq}):
        stream_chat_with_failover("groq", [{"role": "user", "content": "with context"}], [], "s",
                                  groq_messages=[{"role": "user", "content": "without"}])

    assert seen["groq"] == [{"role": "user", "content": "without"}]


def test_groq_tool_schema_lets_optional_parameters_be_null():
    def thesis_stats(mentor: str = "", year: str = "") -> dict:
        """Counts."""
        return {}

    params = _groq_tool_schema(thesis_stats)["function"]["parameters"]

    assert params["properties"]["mentor"] == {"type": ["string", "null"]}
    assert params["required"] == []


def test_execute_groq_tool_call_treats_null_as_not_given():
    def thesis_stats(mentor: str = "", year: str = "") -> dict:
        return {"mentor": mentor, "year": year}

    tool_call = MagicMock()
    tool_call.function.name = "thesis_stats"
    tool_call.function.arguments = '{"mentor": null, "year": "2025"}'

    assert _execute_groq_tool_call({"thesis_stats": thesis_stats}, tool_call) == {"result": {"mentor": "", "year": "2025"}}
