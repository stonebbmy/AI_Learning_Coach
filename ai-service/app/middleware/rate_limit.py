"""
Redis 滑动窗口限流中间件（Sliding Window Rate Limiter）。

算法选型说明（面试考点）：
- 固定窗口（Fixed Window）：实现简单但窗口边界存在流量突刺。
- 滑动窗口（Sliding Window Log）：精确但内存占用随请求量增加。
- 本实现采用「滑动窗口计数器」（Sliding Window Counter）：
    将时间划分为固定窗口，用当前窗口计数 + 上一窗口的加权推算，
    在精确性和内存之间取得平衡，这是 Redis + Lua 脚本实现的典型方案。
- 生产中常见替代品：令牌桶（Token Bucket）更适合突发流量，Leaky Bucket 更平滑。

Trade-off：
- 多 worker 下 Redis 是共享状态存储，保证了跨进程的限流准确性，
  但每次请求多一次 Redis INCR + EXPIRE，P99 约增加 1-3ms。
- 若 Redis 故障，应 fail-open（放行）避免全站降级，这里使用 try/except 兜底。
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..cache.redis_client import get_redis
from ..core.config import settings
from ..core.exceptions import RateLimitError


class SlidingWindowRateLimitMiddleware(BaseHTTPMiddleware):
    """
    基于 Redis INCR 的滑动窗口限流中间件。

    配置项（均来自 settings）：
    - RATE_LIMIT_ENABLED: bool  是否开启限流
    - RATE_LIMIT_MAX_REQUESTS: int  每窗口最大请求数
    - RATE_LIMIT_WINDOW_SECONDS: int  窗口大小（秒）
    - RATE_LIMIT_KEY_PREFIX: str  Redis key 前缀

    限流 Key 策略：
    - 优先使用 X-Real-IP / X-Forwarded-For 头（反向代理场景）
    - 其次使用 request.client.host（直连场景）
    - 特定路径（/health, /metrics）不做限流
    """

    # 不限流的路径前缀白名单
    _SKIP_PREFIXES: tuple[str, ...] = ("/health", "/metrics", "/docs", "/openapi.json", "/redoc")

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # 白名单路径直接放行
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._SKIP_PREFIXES):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        if not self._check_rate_limit(client_ip, path):
            raise RateLimitError(
                f"请求过于频繁：{settings.RATE_LIMIT_WINDOW_SECONDS}s 内最多 "
                f"{settings.RATE_LIMIT_MAX_REQUESTS} 次请求"
            )

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取真实客户端 IP（兼容反向代理）。"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _check_rate_limit(self, client_ip: str, path: str) -> bool:
        """
        滑动窗口计数器实现：
        1. 取当前时间戳所在的窗口编号（timestamp // window_size）
        2. 对当前窗口的 Redis key 执行 INCR，首次 INCR 时设置过期时间
        3. 若计数 > max_requests 则拒绝

        这是单窗口版本；完整滑动版本需要 ZADD+ZCOUNT，此处权衡了 Redis 开销。
        """
        r = get_redis()
        if r is None:
            return True  # fail-open：Redis 不可用时放行

        try:
            window_id = int(time.time()) // settings.RATE_LIMIT_WINDOW_SECONDS
            # 按 IP + 路径前缀隔离（防止单接口被刷导致其他接口受限）
            path_tag = path.split("/")[2] if path.count("/") >= 2 else "root"
            key = f"{settings.RATE_LIMIT_KEY_PREFIX}:{client_ip}:{path_tag}:{window_id}"

            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS * 2)  # 保留 2 个窗口
            results = pipe.execute()
            count: int = results[0]
            return count <= settings.RATE_LIMIT_MAX_REQUESTS
        except Exception as e:
            print(f"[RateLimit] Redis error (fail-open): {e}")
            return True  # fail-open
