"""
智能私教总控层 API（SSE 流式）

端点：POST /api/tutor/chat

工作流程：
1. [安全]  Guardrails 输入校验
2. [编排]  TutorOrchestrator LangGraph 执行（意图分类 → 工具调度 → 构造 Synthesis Prompt）
3. [流式]  LLM 流式生成最终私教回复（SSE）
4. [记忆]  将本轮对话写入 Redis 短期记忆

SSE 事件协议：
  data: <text chunk>              — 正文流
  event: actions, data: [...]    — 执行的动作列表（JSON 数组）
  event: intent, data: <str>     — 分类到的意图
  event: end, data: done         — 流结束
  event: error, data: <msg>      — 错误（流中断）
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from langchain_core.messages import HumanMessage, SystemMessage
from sse_starlette.sse import EventSourceResponse

from ..agents.tutor_orchestrator import (
    _SYNTHESIS_SYSTEM_HEADER,
    get_tutor_orchestrator,
)
from ..core.config import settings
from ..core.llm import llm
from ..guardrails.input_guard import enforce_input
from ..memory.conversation import append_session_message
from ..models.tutor_schemas import TutorRequest, TutorState

_logger = logging.getLogger(__name__)

router = APIRouter()

_ORCHESTRATION_TIMEOUT = settings.TUTOR_ORCHESTRATION_TIMEOUT
_SYNTHESIS_STREAM_TIMEOUT = settings.TUTOR_SYNTHESIS_TIMEOUT


@router.post("/tutor/chat")
async def tutor_chat(request: TutorRequest):
    """
    智能私教统一对话入口（SSE 流式）。

    客户端收到的 SSE 事件顺序：
      1. event:intent   — 分类结果（快速返回，让前端展示"正在思考..."状态）
      2. event:actions  — 执行了哪些工具（前端可展示动作徽章）
      3. data: ...      — 流式正文（私教回复内容）
      4. event:end      — 流结束标志
    """
    # 1. 安全输入校验
    enforce_input(request.question)

    user_id = request.user_id or "anonymous"
    session_id = request.session_id or "tutor_default"

    # 2. 初始化编排状态
    initial_state: TutorState = {
        "user_id": user_id,
        "session_id": session_id,
        "user_message": request.question,
    }

    async def stream_generator():
        # ── Phase 1: 运行编排图（非流式，并行工具调度）────────────────────────
        try:
            orchestrator = get_tutor_orchestrator()
            final_state: TutorState = await asyncio.wait_for(
                orchestrator.ainvoke(initial_state),
                timeout=_ORCHESTRATION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _logger.error("[Tutor] orchestration timeout user=%s", user_id)
            yield {
                "event": "error",
                "data": "私教正在思考中，响应超时，请稍后重试",
            }
            return
        except Exception as e:
            _logger.error("[Tutor] orchestration error user=%s: %s", user_id, e)
            yield {
                "event": "error",
                "data": f"处理请求时发生错误：{str(e)[:120]}",
            }
            return

        # ── 向前端推送意图和动作信息 ──────────────────────────────────────────
        intent = final_state.get("intent", "LEARN")
        actions = final_state.get("tutor_actions", [])

        yield {"event": "intent", "data": intent}

        if actions:
            yield {
                "event": "actions",
                "data": json.dumps(actions, ensure_ascii=False),
            }

        # ── Phase 2: 流式生成私教最终回复 ────────────────────────────────────
        synthesis_prompt = final_state.get("synthesis_prompt", "")
        if not synthesis_prompt:
            yield {"data": "抱歉，我暂时无法处理这个请求，请换一种方式描述或稍后再试。"}
            yield {"event": "end", "data": "done"}
            return

        messages = [
            SystemMessage(content=_SYNTHESIS_SYSTEM_HEADER),
            HumanMessage(content=synthesis_prompt),
        ]

        full_response = ""
        try:
            async for chunk_data in _stream_with_timeout(messages, _SYNTHESIS_STREAM_TIMEOUT):
                full_response += chunk_data
                yield {"data": chunk_data}

        except asyncio.TimeoutError:
            _logger.error("[Tutor] synthesis stream timeout user=%s", user_id)
            yield {"event": "error", "data": "回复生成超时，已获取部分内容"}
        except Exception as e:
            _logger.error("[Tutor] synthesis stream error user=%s: %s", user_id, e)
            if not full_response:
                yield {"event": "error", "data": "生成回复时出错，请重试"}

        yield {"event": "end", "data": "done"}

        # ── Phase 3: 异步保存对话到短期记忆 ──────────────────────────────────
        if full_response:
            asyncio.create_task(
                _save_conversation(session_id, request.question, full_response)
            )

    return EventSourceResponse(stream_generator())


async def _stream_with_timeout(messages: list, timeout: float):
    """
    带超时的 LLM 流式生成器。
    逐 chunk yield 文本，超时时抛 asyncio.TimeoutError。
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def producer():
        try:
            async for chunk in llm.astream(messages):
                text = getattr(chunk, "content", "") or ""
                if text:
                    await queue.put(text)
        except Exception as e:
            _logger.error("[Tutor] llm.astream error: %s", e)
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(producer())
    deadline = asyncio.get_event_loop().time() + timeout

    try:
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                task.cancel()
                raise asyncio.TimeoutError()
            try:
                item = await asyncio.wait_for(queue.get(), timeout=min(remaining, 30.0))
            except asyncio.TimeoutError:
                task.cancel()
                raise
            if item is None:
                break
            yield item
    finally:
        task.cancel()


async def _collect_stream(messages: list) -> str:
    """收集完整流式响应（供内部使用）。"""
    result = ""
    async for chunk in llm.astream(messages):
        text = getattr(chunk, "content", "") or ""
        result += text
    return result


async def _save_conversation(session_id: str, question: str, answer: str) -> None:
    """异步将本轮对话写入 Redis 短期记忆。"""
    try:
        append_session_message(session_id, "user", question)
        append_session_message(session_id, "assistant", answer)
    except Exception as e:
        _logger.warning("[Tutor] save conversation error: %s", e)


# ---------------------------------------------------------------------------
# 辅助端点：更新私教上下文（前端在用户切换大纲/计划后调用）
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from typing import List, Optional


class TutorContextUpdate(BaseModel):
    user_id: str
    current_outline_id: Optional[int] = None
    current_plan_id: Optional[int] = None
    active_topic: str = ""
    progress_rate: float = 0.0
    outline_chapters: List[str] = []
    plan_tasks: List[dict] = []


@router.post("/tutor/context")
async def update_tutor_context(body: TutorContextUpdate):
    """
    前端主动更新用户私教上下文（切换大纲/完成计划时调用）。
    写入 Redis tutor:ctx:{user_id}，TTL 7 天。
    """
    from ..agents.tutor_tools import save_tutor_context
    ctx = body.model_dump(exclude={"user_id"})
    save_tutor_context(body.user_id, ctx)
    return {"status": "ok", "user_id": body.user_id}


@router.get("/tutor/context/{user_id}")
async def get_tutor_context(user_id: str):
    """获取用户当前私教上下文（调试/前端状态同步用）。"""
    from ..agents.tutor_tools import load_tutor_context
    ctx = load_tutor_context(user_id)
    return {"user_id": user_id, "context": ctx}
