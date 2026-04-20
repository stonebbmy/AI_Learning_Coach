
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
from ..prompts.yaml_loader import format_history_block
from ..observability.tracing import build_langfuse_callbacks, structured_log, timer_ms
from ..utils.token_counter import count_tokens
from ..core.config import settings

router = APIRouter()


def _merge_messages_for_prompt(request: ChatRequest) -> str:
    """优先使用客户端显式传入的 messages；否则使用 Redis 中的会话窗口。"""
    if request.messages:
        merged = [{"role": m.role, "content": m.content} for m in request.messages]
    else:
        merged = load_session_messages(request.session_id)
    hb = format_history_block(merged)
    lm = retrieve_long_memory_context(request.session_id, request.question)
    if lm:
        hb = (hb + "\n【长期记忆检索】\n" + lm).strip()
    return hb


@router.post("/chat")
async def chat_with_rag(request: ChatRequest):
    """
    使用 RAG 和流式输出进行问答。

    技术要点:
    1. RAG +（可选）Embedding 重排序
    2. SSE 流式输出
    3. Redis 精确缓存 / Chroma 语义缓存
    4. 短期会话（Redis）+ 可选长期记忆向量
    5. Prompt 自 YAML 加载（版本由 PROMPT_QA_VERSION 控制）
    6. 可选 Langfuse callbacks
    """
    print(f"Received chat request: '{request.question}'")
    qa_chain = get_qa_chain()
    history_block = _merge_messages_for_prompt(request)

    # 缓存短路（面试点：成本与延迟）
    cached = get_exact_cached_answer(request.question) or try_semantic_cache_hit(request.question)
    if cached:

        async def cached_stream():
            yield {"data": cached}
            yield {"event": "end", "data": ""}
            append_session_message(request.session_id, "user", request.question)
            append_session_message(request.session_id, "assistant", cached)
            structured_log(
                "chat_complete",
                session_id=request.session_id,
                latency_ms=0,
                tokens_in=count_tokens(request.question),
                tokens_out=count_tokens(cached),
                cache="hit",
            )

        return EventSourceResponse(cached_stream())

    t0 = timer_ms()
    callbacks = build_langfuse_callbacks()

    async def stream_generator():
        full_answer: list[str] = []
        try:
            payload = {"question": request.question, "history_block": history_block}
            cfg = {"callbacks": callbacks} if callbacks else {}
            async for chunk in qa_chain.astream(payload, config=cfg):
                if chunk:
                    full_answer.append(chunk)
                    yield {"data": chunk}
                    await asyncio.sleep(0.01)
            text = "".join(full_answer)
            yield {"event": "end", "data": ""}

            elapsed = timer_ms() - t0
            tok_in = count_tokens(request.question + history_block)
            tok_out = count_tokens(text)
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

        except Exception as e:
            print(f"[Error] Error during RAG stream: {e}")
            structured_log("chat_error", error=str(e), session_id=request.session_id)
            yield {"event": "error", "data": "处理您的问题时发生错误。"}

    return EventSourceResponse(stream_generator())
