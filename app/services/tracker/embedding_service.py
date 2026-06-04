"""
Embedding service — converts task title + description into a 384-dim vector
using the all-MiniLM-L6-v2 model (runs locally, no API key needed).

The model is downloaded once on first use (~90 MB) and cached by
sentence-transformers in the default HuggingFace cache directory.
"""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dimensions, fast, good semantic quality
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load model once and cache it in memory for the lifetime of the process."""
    return SentenceTransformer(_MODEL_NAME)


def embed_task(title: str, description: str | None = None) -> list[float]:
    """
    Produce a 384-dim embedding for a task.
    Concatenates title and description so both influence similarity.
    """
    text = title.strip()
    if description:
        text = f"{text}. {description.strip()}"
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()
