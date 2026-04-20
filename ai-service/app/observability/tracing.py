from __future__ import annotations

import json
import time
from typing import Any, List

from ..core.config import settings
from ..core.trace import get_request_id


def structured_log(event: str, **fields: Any) -> None:
    """结构化日志（便于接入 ELK / Loki；面试点：可观测性基线）。"""
    payload = {"event": event, "request_id": get_request_id(), **fields}
    print(json.dumps(payload, ensure_ascii=False))


def timer_ms() -> float:
    return time.perf_counter() * 1000.0


def build_langfuse_callbacks() -> List[Any]:
    """若配置了 Langfuse，则返回 CallbackHandler 列表供 LangChain 传入 config['callbacks']。"""
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return []
    try:
        from langfuse.callbacks import CallbackHandler
    except ImportError:
        try:
            from langfuse.langchain import CallbackHandler  # type: ignore
        except ImportError as e:
            print(f"[observability] Langfuse CallbackHandler 不可用: {e}")
            return []
    try:
        handler = CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        return [handler]
    except Exception as e:
        print(f"[observability] Langfuse handler init failed: {e}")
        return []
