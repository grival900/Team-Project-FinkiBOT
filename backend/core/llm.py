from functools import lru_cache

from google import genai
from groq import Groq

from backend.core.config import get_settings


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


@lru_cache
def get_groq_client() -> Groq:
    # no retries - the SDK's own retries took over a minute; we'd rather switch to Gemini
    return Groq(api_key=get_settings().groq_api_key, max_retries=0)
