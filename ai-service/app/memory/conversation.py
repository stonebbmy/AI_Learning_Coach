from __future__ import annotations

import json
from typing import Any, List

from ..core.config import settings
from ..core.trace import get_request_id
from ..cache.redis_client import get_redis


def _session_key(session_id: str) -> str:
    return f"chat:session:{session_id}"


def load_session_messages(session_id: str) -> List[dict[str, Any]]:
    """短期记忆：从 Redis 读取最近 N 轮对话（user/assistant）。"""
    r = get_redis()
    if not r:
        return []
    try:
        key = _session_key(session_id)
        raw_list = r.lrange(key, -2 * settings.CHAT_HISTORY_MAX_TURNS, -1)
        out: List[dict[str, Any]] = []
        for raw in raw_list:
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[rid={get_request_id()}] load session messages failed: {e}")
        return []


def append_session_message(session_id: str, role: str, content: str) -> None:
    r = get_redis()
    if not r:
        return
    try:
        key = _session_key(session_id)
        r.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
        r.expire(key, settings.CHAT_SESSION_TTL_SECONDS)
        # 限制列表长度：保留最近 2 * max_turns 条消息（user+assistant）
        max_len = 2 * settings.CHAT_HISTORY_MAX_TURNS + 2
        r.ltrim(key, -max_len, -1)
    except Exception as e:
        print(f"[rid={get_request_id()}] append session message failed: {e}")
