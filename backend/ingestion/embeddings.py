from functools import lru_cache

from sentence_transformers import SentenceTransformer

from backend.core.config import get_settings


@lru_cache
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(
        get_settings().embedding_model_name,
        # otherwise it downloads an extra, unused 2.2GB safetensors copy
        model_kwargs={"low_cpu_mem_usage": False, "use_safetensors": False},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
