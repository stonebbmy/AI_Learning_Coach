"""
分层上下文管理器（Tiered Context Manager）

解决"上下文过长"问题的主流方案，按优先级组装每次请求的历史上下文：

Tier 1 — 滚动摘要（Rolling Summary）
  Redis key: summary:{session_id}
  将超过阈值的旧对话压缩为 LLM 摘要，永不丢失信息。

Tier 2 — 长期语义记忆（Long-term Memory）
  Chroma collection: session_long_memory
  对当前问题做语义检索，取最相关的历史 Q&A 片段（按 session_id 过滤）。

Tier 3 — 近期滑动窗口（Recent Window）
  Redis List: chat:session:{session_id}
  最近 N 轮完整对话，填满剩余 Token 预算。

触发条件：
  每次写入消息后，若历史消息总数 >= SUMMARIZE_THRESHOLD，
  自动对最旧的一半消息调用 LLM 生成摘要并写回 Redis，裁减原列表。

优势 vs 当前的字符截断：
  - Token 感知：用实际 token 数做预算，而非字符数
  - 信息保留：老内容压缩而非丢弃
  - 相关性：语义检索而非机械保留最近 N 条
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, List

from ..cache.redis_client import get_redis
from ..core.config import settings
from ..utils.token_counter import count_tokens

_logger = logging.getLogger(__name__)

_SUMMARY_KEY_PREFIX = "summary:"
_SESSION_KEY_PREFIX = "chat:session:"


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _summary_key(session_id: str) -> str:
    return f"{_SUMMARY_KEY_PREFIX}{session_id}"


def _session_key(session_id: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{session_id}"


def _load_summary(session_id: str) -> str:
    """从 Redis 读取该 session 的滚动摘要（若不存在返回空字符串）。"""
    r = get_redis()
    if not r:
        return ""
    try:
        val = r.get(_summary_key(session_id))
        return val or ""
    except Exception as e:
        _logger.warning("[ContextManager] load_summary error: %s", e)
        return ""


def _save_summary(session_id: str, summary_text: str) -> None:
    """将摘要写入 Redis，TTL = CHAT_SESSION_TTL_SECONDS * 2（比会话本身活得更久）。"""
    r = get_redis()
    if not r:
        return
    try:
        ttl = settings.CHAT_SESSION_TTL_SECONDS * 2
        r.setex(_summary_key(session_id), ttl, summary_text)
    except Exception as e:
        _logger.warning("[ContextManager] save_summary error: %s", e)


def _load_recent_messages(session_id: str) -> List[dict[str, Any]]:
    """从 Redis List 读取所有历史消息（最多 2 * CHAT_HISTORY_MAX_TURNS 条）。"""
    r = get_redis()
    if not r:
        return []
    try:
        key = _session_key(session_id)
        raw_list = r.lrange(key, -2 * settings.CHAT_HISTORY_MAX_TURNS, -1)
        out = []
        for raw in raw_list:
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
        return out
    except Exception as e:
        _logger.warning("[ContextManager] load_recent_messages error: %s", e)
        return []


def _fit_messages_to_budget(messages: List[dict], budget_tokens: int) -> str:
    """
    从最新消息往回填，直到超出 token 预算。
    保证最近的对话总是被保留。
    """
    if not messages or budget_tokens <= 0:
        return ""
    lines: list[str] = []
    used = 0
    for msg in reversed(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        if not content:
            continue
        line = f"{role}: {content}"
        tokens = count_tokens(line)
        if used + tokens > budget_tokens:
            break
        lines.append(line)
        used += tokens
    if not lines:
        return ""
    lines.reverse()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 核心：组装分层上下文
# ---------------------------------------------------------------------------

async def assemble_context(
    session_id: str,
    question: str,
    max_tokens: int | None = None,
) -> str:
    """
    组装三层上下文字符串，用于注入 Prompt 的 history_block 位置。

    Args:
        session_id: 会话 ID
        question:   当前用户问题（用于长期记忆语义检索）
        max_tokens: Token 预算上限，默认取 settings.CONTEXT_MAX_TOKENS

    Returns:
        组合好的历史上下文字符串，空时返回 ""
    """
    budget = max_tokens if max_tokens is not None else settings.CONTEXT_MAX_TOKENS
    parts: list[str] = []

    # ── Tier 1：滚动摘要（最优先，已压缩，token 消耗小）──────────────────────
    summary = _load_summary(session_id)
    if summary:
        summary_block = f"【对话摘要（历史压缩）】\n{summary}"
        tok = count_tokens(summary_block)
        if budget - tok > 200:  # 至少留 200 token 给后两层
            parts.append(summary_block)
            budget -= tok

    # ── Tier 2：长期语义记忆（相关历史 Q&A）────────────────────────────────
    if settings.LONG_MEMORY_ENABLED and budget > 500:
        try:
            from ..memory.long_term import retrieve_long_memory_context
            ltm = await asyncio.to_thread(
                retrieve_long_memory_context, session_id, question
            )
            if ltm:
                ltm_block = f"【相关历史问答】\n{ltm}"
                tok = count_tokens(ltm_block)
                if tok <= budget - 200:
                    parts.append(ltm_block)
                    budget -= tok
        except Exception as e:
            _logger.warning("[ContextManager] long_memory retrieve error: %s", e)

    # ── Tier 3：近期滑动窗口（填满剩余预算）────────────────────────────────
    if budget > 50:
        recent = _load_recent_messages(session_id)
        recent_text = _fit_messages_to_budget(recent, budget - 30)
        if recent_text:
            parts.append(f"【近期对话】\n{recent_text}")

    if not parts:
        return ""
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 滚动摘要：超阈值时压缩旧消息
# ---------------------------------------------------------------------------

_SUMMARIZE_SYSTEM = """你是一个对话摘要助手。请将以下多轮对话压缩为简洁的要点摘要，保留关键知识点、用户已掌握的概念、待解决的疑问。摘要需在 300 字以内，使用中文。"""


async def maybe_summarize_session(session_id: str) -> None:
    """
    若该 session 消息总数 >= SUMMARIZE_THRESHOLD * 2，
    对最旧的一半消息做 LLM 摘要压缩，写回 Redis，并裁减原列表。

    设计：
    - 摘要与已有摘要合并（滚动累积），防止长期使用后摘要丢失上文
    - 只在超阈值时触发，避免每次都调 LLM
    - 异步执行，不阻塞主响应链路
    """
    r = get_redis()
    if not r:
        return

    try:
        key = _session_key(session_id)
        total = r.llen(key)
        threshold = settings.SUMMARIZE_THRESHOLD * 2  # 消息条数（user+assistant 各算1条）
        if total < threshold:
            return

        # 取最旧的一半消息用于摘要
        half = total // 2
        old_raw = r.lrange(key, 0, half - 1)
        old_messages = []
        for raw in old_raw:
            try:
                old_messages.append(json.loads(raw))
            except Exception:
                continue

        if not old_messages:
            return

        # 构造摘要请求
        conversation_text = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')[:300]}"
            for m in old_messages
        )

        # 合并已有摘要（滚动）
        existing_summary = _load_summary(session_id)
        if existing_summary:
            conversation_text = (
                f"【已有摘要】\n{existing_summary}\n\n"
                f"【新增对话】\n{conversation_text}"
            )

        from langchain_core.messages import HumanMessage, SystemMessage
        from ..core.llm import llm_for_structured

        messages = [
            SystemMessage(content=_SUMMARIZE_SYSTEM),
            HumanMessage(content=conversation_text),
        ]

        resp = await asyncio.wait_for(
            llm_for_structured.ainvoke(messages),
            timeout=20.0,
        )
        new_summary = (resp.content or "").strip()

        if new_summary:
            _save_summary(session_id, new_summary)
            # 裁剪 Redis List，保留最新的后半部分
            r.ltrim(key, half, -1)
            _logger.info(
                "[ContextManager] session=%s summarized %d messages, list trimmed",
                session_id, half,
            )

    except asyncio.TimeoutError:
        _logger.warning("[ContextManager] summarize timeout for session=%s", session_id)
    except Exception as e:
        _logger.warning("[ContextManager] summarize error session=%s: %s", session_id, e)
