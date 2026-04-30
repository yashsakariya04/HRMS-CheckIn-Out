"""
app/dependencies/redis.py — Redis Dependency
=============================================
Provides a FastAPI dependency that yields a shared aioredis client.
Used by the AI classifier for caching classification results.
"""

import redis.asyncio as aioredis

from app.core.config import settings

_pool: aioredis.Redis | None = None


def get_redis_pool() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _pool


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency — yields the shared Redis client."""
    return get_redis_pool()
