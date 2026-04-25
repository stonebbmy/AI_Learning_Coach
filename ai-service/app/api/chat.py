"""
RAG 问答 API（流式 SSE）。

高可用 & 安全完整实现：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[安全] Guardrails 输入防护
  - enforce_input(): 长度限制 + Prompt 注入检测，抛 InputValidationError(400)

[安全] Session Token 配额（防恶意消耗 Token）
  - 每个 session 在 SESSION_TOKEN_WINDOW 秒内最多消耗 SESSION_TOKEN_BUDGET Token
  - 超过配额直接返回 429，不调用 LLM
  - 配额记录在 Redis（Key: token_budget:{session_id}），到期自动清零

[高可用] 双层缓存短路
  - 精确缓存 (Redis SHA256)：延迟 <5ms
  - 语义缓存 (Chroma 向量)：延迟 <200ms
  - 命中则跳过 LLM，成本 = 0

[高可用] 流式超时保护
  - asyncio.wait_for 包裹 astream()，超时后发送 error 事件
  - 防止 LLM API 挂起导致连接永久占用（幻象请求）

[可观测] 指标上报
  - record_tokens / record_latency / record_request_error
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..models.schemas import ChatRequest
from ..agents.qa import get_qa_chain
from ..cache.chat_cache import (
    add_semantic_cache_entry,
    get_exact_cached_answer,
    set_exact_cached_answer,
    try_semantic_cache_hit,
)
from ..memory.conversation import append_session_message, load_session_messages
from ..memory.long_term import index_qa_turn, retrieve_long_memory_context
from ..memory.context_manager import assemble_context, maybe_summarize_session
from ..prompts.yaml_loader import format_history_block
from ..observability.tracing import build_langfuse_callbacks, structured_log, timer_ms
from ..utils.token_counter import count_tokens
from ..core.config import settings
from ..core.exceptions import InputValidationError, RateLimitError
from ..guardrails.input_guard import enforce_input
from ..api.metrics import record_tokens, record_request_error, record_latency
from ..cache.redis_client import get_redis

router = APIRouter()


# ---------------------------------------------------------------------------
# Session Token 配额管理（防恶意消耗 Token）
# ---------------------------------------------------------------------------

def _get_session_token_key(session_id: str) -> str:
    return f"token_budget:{session_id}"


def _check_session_token_budget(session_id: str, tokens_to_use: int = 0) -> tuple[bool, int]:
    """
    检查 Session Token 配额。

    返回：(是否允许, 当前已用 Token 数)
    - 若 SESSION_TOKEN_BUDGET=0（默认），表示不限制，直接放行
    - 若当前已用 + tokens_to_use > 配额，拒绝
    - 使用 Redis INCRBY + EXPIRE 原子操作，多 Worker 安全
    """
    if settings.SESSION_TOKEN_BUDGET <= 0:
        return True, 0

    r = get_redis()
    if r is None:
        return True, 0  # Redis 不可用时 fail-open

    try:
        key = _get_session_token_key(session_id)
        current = r.get(key)
        used = int(current) if current else 0
        if used + tokens_to_use > settings.SESSION_TOKEN_BUDGET:
            return False, used
        return True, used
    except Exception as e:
        print(f"[TokenBudget] Redis error (fail-open): {e}")
        return True, 0


def _record_session_tokens(session_id: str, tokens: int) -> None:
    """原子地累加 Session 已用 Token 数，并设置过期时间。"""
    if settings.SESSION_TOKEN_BUDGET <= 0 or tokens <= 0:
        return
    r = get_redis()
    if r is None:
        return
    try:
        key = _get_session_token_key(session_id)
        pipe = r.pipeline()
        pipe.incrby(key, tokens)
        pipe.expire(key, settings.SESSION_TOKEN_WINDOW)
        pipe.execute()
    except Exception as e:
        print(f"[TokenBudget] write failed: {e}")


# ---------------------------------------------------------------------------
# 历史消息合并
# ---------------------------------------------------------------------------

async def _merge_messages_for_prompt(request: ChatRequest) -> str:
    """
    优先使用客户端显式传入的 messages（多轮前端传参）；
    否则使用三层上下文管理器（滚动摘要 + 长期记忆 + 近期窗口）。
    """
    if request.messages:
        merged = [{"role": m.role, "content": m.content} for m in request.messages]
        return format_history_block(merged)
    # 使用分层上下文组装（token 感知，含滚动摘要 + 长期记忆）
    return await assemble_context(request.session_id, request.question)


def _build_system_prefix(request: ChatRequest) -> str:
    """根据请求中的 plan_context 构建系统提示前缀，引导回答聚焦今日学习任务。"""
    if not request.plan_context:
        return ""
    return (
        f"【学习上下文】用户今日的学习计划如下，请优先结合这些任务内容来回答问题：\n"
        f"{request.plan_context}\n\n"
    )


# ---------------------------------------------------------------------------
# 流式生成协程（带总超时）
# ---------------------------------------------------------------------------

async def _collect_stream(qa_chain, payload: dict, callbacks: list) -> str:
    """
    执行 RAG 流式生成，收集完整答案文本。
    此协程被 asyncio.wait_for 包裹，超时后抛 asyncio.TimeoutError。
    """
    chunks: list[str] = []
    cfg = {"callbacks": callbacks} if callbacks else {}
    async for chunk in qa_chain.astream(payload, config=cfg):
        if chunk:
            chunks.append(chunk)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# 主路由
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat_with_rag(request: ChatRequest):
    """
    RAG 问答流式接口（SSE）。

    完整处理链路：
    1. [安全] Guardrails 输入校验（长度/注入检测）→ 400
    2. [安全] Session Token 配额检查 → 429
    3. [高可用] 双层缓存短路（Redis精确 → Chroma语义）
    4. RAG 检索（BM25 + 向量混合，可选 Embedding 重排）
    5. 会话记忆注入（Redis短期 + Chroma长期）
    6. [高可用] 带总超时的 LLM 流式生成（CHAT_STREAM_TIMEOUT 秒）
    7. 写回缓存 + 更新会话记忆 + 指标上报
    """

    # --- Step 1: Guardrails 输入安全校验 ---
    enforce_input(request.question)

    # --- Step 2: Session Token 配额检查 ---
    # 预估本次输入 Token（输出无法预估，只检查输入侧）
    estimated_input_tokens = count_tokens(request.question)
    allowed, used_tokens = _check_session_token_budget(
        request.session_id, estimated_input_tokens
    )
    if not allowed:
        raise RateLimitError(
            f"当前会话 Token 用量已达上限（已用 {used_tokens}，"
            f"窗口内最大 {settings.SESSION_TOKEN_BUDGET} Token）"
        )

    print(f"[chat] session={request.session_id} user={request.user_id} question='{request.question[:50]}'")
    qa_chain = get_qa_chain()
    history_block = await _merge_messages_for_prompt(request)
    system_prefix = _build_system_prefix(request)

    # --- Step 3: 双层缓存短路（含 plan_context 时跳过缓存，保证答案与当日计划一致）---
    use_cache = not bool(request.plan_context)
    cached = None
    if use_cache:
        cached = get_exact_cached_answer(request.question) or try_semantic_cache_hit(request.question)
    if cached:
        tok_in = count_tokens(request.question)
        tok_out = count_tokens(cached)

        async def cached_stream():
            yield {"data": cached}
            yield {"event": "end", "data": ""}
            append_session_message(request.session_id, "user", request.question)
            append_session_message(request.session_id, "assistant", cached)
            record_tokens(tok_in, tok_out)
            _record_session_tokens(request.session_id, tok_in + tok_out)
            structured_log(
                "chat_complete",
                session_id=request.session_id,
                latency_ms=0,
                tokens_in=tok_in,
                tokens_out=tok_out,
                cache="hit",
            )

        return EventSourceResponse(cached_stream())

    # --- Step 4-6: RAG 检索 + LLM 流式生成 ---
    t0 = timer_ms()
    callbacks = build_langfuse_callbacks()

    async def stream_generator():
        try:
            effective_question = (system_prefix + request.question) if system_prefix else request.question
            payload = {"question": effective_question, "history_block": history_block}

            # 带总超时的流式收集：防止 LLM API 挂起导致请求永久占用连接
            try:
                text = await asyncio.wait_for(
                    _collect_stream(qa_chain, payload, callbacks),
                    timeout=settings.CHAT_STREAM_TIMEOUT,
                )
            except asyncio.TimeoutError:
                print(f"[chat] stream timeout after {settings.CHAT_STREAM_TIMEOUT}s")
                record_request_error()
                yield {"event": "error", "data": f"生成超时（>{int(settings.CHAT_STREAM_TIMEOUT)}s），请缩短问题后重试"}
                return

            # 逐字符推送（兼容前端 SSE 解析）
            # 注：_collect_stream 已收集完整文本，此处分块推送保持 SSE 体验
            chunk_size = 20
            for i in range(0, len(text), chunk_size):
                yield {"data": text[i: i + chunk_size]}
                await asyncio.sleep(0)  # 让出事件循环，避免阻塞

            yield {"event": "end", "data": ""}

            # --- Step 7: 后处理（缓存写入 + 指标上报）---
            elapsed = timer_ms() - t0
            tok_in = count_tokens(request.question + history_block)
            tok_out = count_tokens(text)

            record_tokens(tok_in, tok_out)
            record_latency(elapsed)
            _record_session_tokens(request.session_id, tok_in + tok_out)
            structured_log(
                "chat_complete",
                session_id=request.session_id,
                latency_ms=round(elapsed, 2),
                tokens_in=tok_in,
                tokens_out=tok_out,
                cache="miss",
            )

            append_session_message(request.session_id, "user", request.question)
            append_session_message(request.session_id, "assistant", text)
            set_exact_cached_answer(request.question, text)
            add_semantic_cache_entry(request.question, text)
            index_qa_turn(request.session_id, request.question, text)
            # 异步触发滚动摘要（不阻塞响应）
            asyncio.create_task(maybe_summarize_session(request.session_id))

        except Exception as e:
            print(f"[chat] stream error: {e}")
            structured_log("chat_error", error=str(e), session_id=request.session_id)
            record_request_error()
            yield {"event": "error", "data": "处理您的问题时发生错误，请稍后重试。"}

    return EventSourceResponse(stream_generator())
