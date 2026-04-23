"""
统一异常定义与 FastAPI 全局异常处理器。

设计原则：
- 业务异常继承自 AppException，携带 HTTP 状态码 + 业务错误码 + 中文描述
- FastAPI 的 exception_handler 统一序列化为 JSON，不向客户端暴露内部堆栈
- 所有未预期异常均被兜底处理，返回 500 但打印完整错误供排查
"""

from __future__ import annotations

import traceback
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# 业务异常基类
# ---------------------------------------------------------------------------

class AppException(Exception):
    """所有业务异常的基类。继承时指定 status_code、code 和默认 message。"""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "服务内部错误", detail: Optional[Any] = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class RateLimitError(AppException):
    """请求频率超过限制。"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "请求过于频繁，请稍后重试"):
        super().__init__(message)


class AuthError(AppException):
    """API Key 认证失败。"""
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTH_FAILED"

    def __init__(self, message: str = "API Key 无效或缺失"):
        super().__init__(message)


class KnowledgeBaseEmptyError(AppException):
    """知识库为空，无法进行 RAG 检索。"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "KNOWLEDGE_BASE_EMPTY"

    def __init__(self, message: str = "知识库为空，请先上传学习资料"):
        super().__init__(message)


class InputValidationError(AppException):
    """用户输入未通过 Guardrails 校验（长度、注入检测等）。"""
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INPUT_INVALID"

    def __init__(self, message: str = "输入内容不合规"):
        super().__init__(message)


class LLMError(AppException):
    """大模型调用失败（超时、API 错误等）。"""
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "LLM_ERROR"

    def __init__(self, message: str = "大模型服务调用失败，请稍后重试", detail: Any = None):
        super().__init__(message, detail)


class VectorStoreError(AppException):
    """向量数据库操作失败。"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "VECTOR_STORE_ERROR"

    def __init__(self, message: str = "向量数据库服务异常", detail: Any = None):
        super().__init__(message, detail)


# ---------------------------------------------------------------------------
# 注册到 FastAPI 应用的函数
# ---------------------------------------------------------------------------

def _make_error_response(
    status_code: int,
    code: str,
    message: str,
    detail: Any = None,
) -> JSONResponse:
    """统一的 JSON 错误响应格式。"""
    body: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


def     register_exception_handlers(app: FastAPI) -> None:
    """将所有异常处理器注册到 FastAPI 应用实例。在 main.py 中调用一次。"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """统一处理所有业务异常。"""
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic 请求体校验失败（422）：返回友好的中文提示。"""
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = " -> ".join(str(loc) for loc in first.get("loc", []))
        msg = first.get("msg", "参数错误")
        return _make_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=f"请求参数错误：{field} {msg}",
            detail=errors,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """兜底处理所有未预期异常：打印堆栈、返回 500。"""
        print(f"[UNHANDLED_EXCEPTION] {request.method} {request.url.path}")
        print(traceback.format_exc())
        return _make_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="服务内部错误，请联系管理员",
        )
