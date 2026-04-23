"""
可选 API Key 鉴权中间件。

设计说明（面试考点）：
- 当 API_KEY_ENABLED=false 时完全透明，不影响现有功能；
  生产部署时开启，防止接口裸奔。
- Key 存储在 settings.API_KEYS（逗号分隔的多 Key 列表），
  支持 Key 轮换（新旧 Key 并存一段时间再下线旧 Key）。
- 使用 secrets.compare_digest 做常量时间比较，防止 timing attack。
- 鉴权失败返回 401，不暴露是"Key 不存在"还是"Key 错误"（防枚举）。

生产扩展方向：
- 将 API Key 存入 Redis，支持动态添加/吊销（无需重启）
- 结合 JWT 做更细粒度的权限控制（用户级别的速率限制）
- 接入 OAuth2/OIDC 做企业级认证
"""

from __future__ import annotations

import secrets
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.config import settings
from ..core.exceptions import AuthError


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    从请求头 X-API-Key 中提取并验证 API Key。

    跳过鉴权的路径：/health、/docs、/openapi.json、/redoc
    """

    _SKIP_PREFIXES: tuple[str, ...] = ("/health", "/docs", "/openapi.json", "/redoc", "/metrics")

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # 预处理 Key 集合，避免每次请求重新分割
        self._valid_keys: set[str] = {
            k.strip() for k in settings.API_KEYS.split(",") if k.strip()
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.API_KEY_ENABLED:
            return await call_next(request)

        # 白名单路径跳过鉴权
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._SKIP_PREFIXES):
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if not self._is_valid(provided_key):
            raise AuthError("X-API-Key 无效或缺失，请检查请求头")

        return await call_next(request)

    def _is_valid(self, key: str) -> bool:
        """使用常量时间比较防止 timing attack。"""
        if not key or not self._valid_keys:
            return False
        return any(secrets.compare_digest(key, valid) for valid in self._valid_keys)
