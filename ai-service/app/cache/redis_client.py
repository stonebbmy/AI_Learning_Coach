from __future__ import annotations

import redis

from ..core.config import settings

_client: redis.Redis | None = None
_redis_failed: bool = False


def get_redis() -> redis.Redis | None:
    """同步 Redis 客户端；未启用或连接失败时返回 None（调用方降级）。"""
    global _client, _redis_failed
    if not settings.REDIS_ENABLED or _redis_failed:
        return None
    if _client is None:
        try:
            r = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            r.ping()
            _client = r
        except Exception as e:
            print(f"[redis] unavailable, cache/session disabled: {e}")
            _redis_failed = True
            return None
    return _client
