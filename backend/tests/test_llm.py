from backend.core.llm import get_groq_client


def test_groq_client_disables_the_sdks_own_retries():
    # the SDK's retries took over a minute; we switch to Gemini instead
    assert get_groq_client().max_retries == 0
