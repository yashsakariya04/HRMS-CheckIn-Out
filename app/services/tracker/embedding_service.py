import httpx
import logging
import os
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768


async def get_embedding(text_content: str) -> list[float]:
    """
    Get 768-dimensional embedding from Google Gemini API (gemini-embedding-2).
    Falls back to a zero vector in development if GEMINI_API_KEY is not set.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        if settings.APP_ENV == "development":
            logger.warning("GEMINI_API_KEY is not configured in development. Returning a dummy 768-dimensional vector.")
            return [0.0] * 768
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured in the application environment settings."
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={api_key}"
    payload = {
        "model": "models/gemini-embedding-2",
        "content": {
            "parts": [{"text": text_content}]
        },
        "outputDimensionality": 768
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["embedding"]["values"]
    except Exception as e:
        logger.error(f"Error fetching embedding from Gemini: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embedding for the task: {str(e)}"
        )


# Alias for backward compatibility with any callers using embed_task
async def embed_task(title: str, description: str | None = None) -> list[float]:
    text = title.strip()
    if description:
        text = f"{text}. {description.strip()}"
    return await get_embedding(text)
