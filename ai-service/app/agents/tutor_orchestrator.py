"""
智能私教编排器（TutorOrchestrator）

架构：LangGraph 0.2.x StateGraph，5 个串行节点

节点流程：
  load_context → classify_intent → dispatch_tools → build_synthesis → persist_state → END

各节点职责：
  1. load_context   : 从 Redis 读取用户学习状态和短期对话记忆
  2. classify_intent: 用 LLM 对用户意图分类（ONBOARD/PLAN/LEARN/REVIEW/PROGRESS/QUIZ/EXPLORE）
  3. dispatch_tools : 按意图并行调度工具（RAG / 笔记检索 / 联网 / 测验生成 / 间隔复习）
  4. build_synthesis: 汇总所有工具结果，构造最终 Synthesis Prompt
  5. persist_state  : 将会话状态写回 Redis
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from ..core.config import settings
from ..core.llm import ainvoke_with_retry, llm_for_structured
from ..memory.conversation import load_session_messages
from ..models.tutor_schemas import IntentResult, TutorState
from .tutor_tools import (
    load_tutor_context,
    save_tutor_context,
    tool_generate_quiz,
    tool_rag_answer,
    tool_search_knowledge,
    tool_spaced_review,
    tool_web_research,
    tool_get_plan_context,
)

_logger = logging.getLogger(__name__)

# ── 意图 → 工具映射 ──────────────────────────────────────────────────────────
_INTENT_TOOLS: Dict[str, List[str]] = {
    "ONBOARD":  ["search_knowledge"],
    "PLAN":     ["search_knowledge"],
    "LEARN":    ["search_knowledge", "rag_answer", "web_research"],
    "REVIEW":   ["search_knowledge", "spaced_review"],
    "PROGRESS": [],                                      # 纯状态读取，无需外部工具
    "QUIZ":     ["search_knowledge", "generate_quiz"],
    "EXPLORE":  ["web_research", "search_knowledge", "rag_answer"],
}

# 意图分类超时（秒）— 使用 config，环境变量可覆盖
_INTENT_TIMEOUT = settings.TUTOR_INTENT_TIMEOUT

# ---------------------------------------------------------------------------
# 节点 1：加载用户上下文
# ---------------------------------------------------------------------------

async def _load_context(state: TutorState) -> TutorState:
    """
    从 Redis 加载：
    - tutor:ctx:{user_id}  → 大纲/计划/进度/活跃主题
    - chat:session:{session_id} → 最近对话记忆
    """
    user_id = state.get("user_id", "anonymous")
    session_id = state.get("session_id", "tutor_default")

    # 从 Redis 读取 Tutor 持久化状态
    ctx = load_tutor_context(user_id)

    updates: TutorState = {
        "current_outline_id": ctx.get("current_outline_id"),
        "current_plan_id": ctx.get("current_plan_id"),
        "active_topic": ctx.get("active_topic", ""),
        "progress_rate": float(ctx.get("progress_rate", 0.0)),
        "outline_chapters": ctx.get("outline_chapters", []),
        "plan_tasks": ctx.get("plan_tasks", []),
        # 短期对话记忆（最近 N 轮）
        "chat_history": load_session_messages(session_id),
    }

    _logger.info(
        "[Tutor] load_context user=%s outline_id=%s plan_id=%s history_len=%d",
        user_id,
        updates.get("current_outline_id"),
        updates.get("current_plan_id"),
        len(updates["chat_history"]),
    )
    return {**state, **updates}


# ---------------------------------------------------------------------------
# 节点 2：意图分类
# ---------------------------------------------------------------------------

_INTENT_SYSTEM = """你是一个意图分类器，专门分析用户在 AI 学习教练场景下的学习意图。

意图类别及触发场景：
- ONBOARD  : 用户首次使用、表示想学习某个新领域、提到学习目标
- PLAN     : 询问今天/本周学什么、要求制定计划、问学习安排
- LEARN    : 提出知识性问题、要求讲解某个概念或技术、"什么是/怎么理解"
- REVIEW   : 要求复习、回顾之前学过的内容、"帮我复习"
- PROGRESS : 汇报完成情况、"做完了/学完了/完成了"、查看进度
- QUIZ     : 主动要求测验、"考考我"、"出几道题"
- EXPLORE  : 探索超出当前大纲的新话题、比较两个技术方案、"xxx和yyy的区别"

根据用户消息和上下文，选择最匹配的一个意图，并列出需要调用的工具。

工具列表：search_knowledge / rag_answer / web_research / spaced_review / generate_quiz

只输出 JSON，格式：{"intent": "...", "sub_tasks": [...], "reason": "..."}"""


async def _classify_intent(state: TutorState) -> TutorState:
    """使用 LLM 对用户消息进行意图分类，设置 intent 和 sub_tasks。"""
    user_message = state.get("user_message", "")
    active_topic = state.get("active_topic", "")
    history = state.get("chat_history", [])

    # 构造分类上下文
    history_text = ""
    if history:
        recent = history[-4:]  # 最近 2 轮
        history_text = "\n".join(
            f"{m.get('role','?')}: {m.get('content','')[:100]}" for m in recent
        )

    context_block = f"当前活跃主题：{active_topic or '无'}"
    if history_text:
        context_block += f"\n最近对话：\n{history_text}"

    prompt = f"{context_block}\n\n用户消息：{user_message}"

    try:
        messages = [
            SystemMessage(content=_INTENT_SYSTEM),
            HumanMessage(content=prompt),
        ]
        resp = await asyncio.wait_for(
            llm_for_structured.ainvoke(messages),
            timeout=_INTENT_TIMEOUT,
        )
        text = resp.content.strip()
        # 解析 JSON
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        intent = parsed.get("intent", "LEARN").upper()
        sub_tasks = parsed.get("sub_tasks", _INTENT_TOOLS.get(intent, []))
        reason = parsed.get("reason", "")
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
        _logger.warning("[Tutor] classify_intent fallback to LEARN: %s", e)
        intent = "LEARN"
        sub_tasks = _INTENT_TOOLS["LEARN"]
        reason = "分类失败，降级为 LEARN"

    # 用映射表确保工具列表合理
    if not sub_tasks:
        sub_tasks = _INTENT_TOOLS.get(intent, [])

    _logger.info(
        "[Tutor] classify_intent user=%s intent=%s sub_tasks=%s reason=%s",
        state.get("user_id"), intent, sub_tasks, reason,
    )
    return {**state, "intent": intent, "sub_tasks": sub_tasks}


# ---------------------------------------------------------------------------
# 节点 3：并行工具调度
# ---------------------------------------------------------------------------

async def _dispatch_tools(state: TutorState) -> TutorState:
    """根据 sub_tasks 并行调度工具，结果写入对应字段。"""
    user_message = state.get("user_message", "")
    user_id = state.get("user_id", "anonymous")
    session_id = state.get("session_id", "tutor_default")
    intent = state.get("intent", "LEARN")
    sub_tasks = state.get("sub_tasks", [])
    active_topic = state.get("active_topic", "") or user_message[:50]
    plan_tasks = state.get("plan_tasks", [])
    outline_chapters = state.get("outline_chapters", [])
    chat_history = state.get("chat_history", [])

    updates: Dict[str, Any] = {
        "notes_context": "",
        "rag_answer": "",
        "web_context": "",
        "progress_summary": {},
        "quiz_questions": [],
        "review_items": "",
        "tutor_actions": [],
    }
    actions: List[str] = []

    # 构造历史 block（供 RAG 使用）
    history_block = ""
    if chat_history:
        recent = chat_history[-6:]
        history_block = "\n".join(
            f"{m.get('role','?')}: {m.get('content','')[:150]}" for m in recent
        )

    # ── 并行执行工具集 ────────────────────────────────────────────────────────

    async def run_search_knowledge():
        if "search_knowledge" not in sub_tasks:
            return
        result = await tool_search_knowledge(user_message, user_id)
        if result:
            updates["notes_context"] = result
            actions.append("📚 搜索知识库")

    async def run_rag_answer():
        if "rag_answer" not in sub_tasks:
            return
        result = await tool_rag_answer(user_message, history_block, user_id)
        if result:
            updates["rag_answer"] = result
            actions.append("🔍 RAG 问答检索")

    async def run_web_research():
        if "web_research" not in sub_tasks:
            return
        result = await tool_web_research(user_message)
        if result:
            updates["web_context"] = result
            actions.append("🌐 联网检索")

    async def run_spaced_review():
        if "spaced_review" not in sub_tasks:
            return
        result = await tool_spaced_review(user_id, session_id, active_topic)
        if result:
            updates["review_items"] = result
            actions.append("🔄 间隔复习内容")

    async def run_generate_quiz():
        if "generate_quiz" not in sub_tasks:
            return
        context = updates.get("notes_context", "") or updates.get("rag_answer", "")
        questions = await tool_generate_quiz(active_topic, context)
        if questions:
            updates["quiz_questions"] = questions
            actions.append("📝 生成测验题")

    # 并行执行所有工具（相互独立）
    await asyncio.gather(
        run_search_knowledge(),
        run_rag_answer(),
        run_web_research(),
        run_spaced_review(),
        return_exceptions=True,  # 单个工具失败不影响整体
    )

    # quiz 依赖 search_knowledge 结果，需串行（但已有超时兜底）
    if "generate_quiz" in sub_tasks:
        await run_generate_quiz()

    # PLAN / PROGRESS 意图：补充计划上下文
    if intent in ("PLAN", "PROGRESS", "ONBOARD"):
        plan_ctx = await tool_get_plan_context(plan_tasks, outline_chapters)
        if plan_ctx:
            updates["progress_summary"] = {"plan_context": plan_ctx}
            if intent == "PROGRESS":
                actions.append("📊 读取学习进度")

    updates["tutor_actions"] = actions
    _logger.info("[Tutor] dispatch_tools actions=%s", actions)
    return {**state, **updates}


# ---------------------------------------------------------------------------
# 节点 4：构造 Synthesis Prompt
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM_HEADER = """你是用户的专属 AI 学习私教，拥有完整的教学上下文和专业的教学能力。

私教原则：
- 主动教学：不只回答问题，主动推进学习进度、检测理解程度
- 上下文感知：结合用户的大纲、计划、进度给出个性化建议
- 激励驱动：用鼓励性语言，帮助用户建立学习信心
- 深浅结合：先给核心概念，再展开细节，最后联系实践

回复要求：
- 语言：中文，专业但不生硬
- 长度：适中（200-600 字），避免信息过载
- 结构：适当使用小标题、列表、代码块
- 结尾：提出一个引导性问题或下一步建议"""


async def _build_synthesis(state: TutorState) -> TutorState:
    """将所有工具结果汇总为 Synthesis Prompt，供 API 层流式调用。"""
    user_message = state.get("user_message", "")
    intent = state.get("intent", "LEARN")
    active_topic = state.get("active_topic", "")
    progress_rate = state.get("progress_rate", 0.0)
    outline_chapters = state.get("outline_chapters", [])
    plan_tasks = state.get("plan_tasks", [])

    notes_context = state.get("notes_context", "")
    rag_answer = state.get("rag_answer", "")
    web_context = state.get("web_context", "")
    quiz_questions = state.get("quiz_questions", [])
    review_items = state.get("review_items", "")
    progress_summary = state.get("progress_summary", {})

    # 构造上下文块
    context_parts: List[str] = [
        f"【学习意图】{intent}",
        f"【用户消息】{user_message}",
    ]

    if active_topic:
        context_parts.append(f"【当前主题】{active_topic}")

    if progress_rate > 0:
        context_parts.append(f"【总体进度】{progress_rate * 100:.0f}%")

    if outline_chapters:
        chapters_str = "、".join(outline_chapters[:5])
        context_parts.append(f"【大纲章节】{chapters_str}")

    if plan_tasks:
        pending = [t for t in plan_tasks if t.get("status") not in ("done", "completed", "DONE")]
        if pending:
            task_desc = "、".join(
                t.get("description", t.get("name", "任务")) for t in pending[:3]
            )
            context_parts.append(f"【今日待完成任务】{task_desc}")

    if progress_summary.get("plan_context"):
        context_parts.append(f"【计划完成情况】{progress_summary['plan_context']}")

    # 知识内容块
    knowledge_parts: List[str] = []
    if rag_answer:
        knowledge_parts.append(f"=== RAG 检索答案 ===\n{rag_answer[:2000]}")
    if notes_context:
        knowledge_parts.append(f"=== 知识库相关内容 ===\n{notes_context[:2000]}")
    if web_context:
        knowledge_parts.append(f"=== 联网检索结果 ===\n{web_context[:1500]}")
    if review_items:
        knowledge_parts.append(f"=== 复习内容 ===\n{review_items[:1500]}")
    if quiz_questions:
        quiz_text = json.dumps(quiz_questions[:3], ensure_ascii=False, indent=2)
        knowledge_parts.append(f"=== 已生成测验题（请向用户呈现）===\n{quiz_text}")

    synthesis_prompt = "\n\n".join(context_parts)
    if knowledge_parts:
        synthesis_prompt += "\n\n" + "\n\n".join(knowledge_parts)

    return {**state, "synthesis_prompt": synthesis_prompt}


# ---------------------------------------------------------------------------
# 节点 5：持久化 Tutor 状态到 Redis
# ---------------------------------------------------------------------------

async def _persist_state(state: TutorState) -> TutorState:
    """将本轮更新后的 Tutor 上下文写回 Redis。"""
    user_id = state.get("user_id", "anonymous")

    ctx_to_save = {
        "current_outline_id": state.get("current_outline_id"),
        "current_plan_id": state.get("current_plan_id"),
        "active_topic": state.get("active_topic", ""),
        "progress_rate": state.get("progress_rate", 0.0),
        "outline_chapters": state.get("outline_chapters", []),
        "plan_tasks": state.get("plan_tasks", []),
    }

    # 异步执行（不阻塞响应流）
    await asyncio.to_thread(save_tutor_context, user_id, ctx_to_save)
    _logger.info("[Tutor] persist_state user=%s saved", user_id)
    return state


# ---------------------------------------------------------------------------
# 图构建与缓存
# ---------------------------------------------------------------------------

_tutor_graph = None


def get_tutor_orchestrator():
    """
    懒加载并缓存 TutorOrchestrator LangGraph 实例。
    使用 StateGraph 模式（与 planner_graph 完全一致）。
    """
    global _tutor_graph
    if _tutor_graph is not None:
        return _tutor_graph

    graph = StateGraph(TutorState)

    graph.add_node("load_context", _load_context)
    graph.add_node("classify_intent", _classify_intent)
    graph.add_node("dispatch_tools", _dispatch_tools)
    graph.add_node("build_synthesis", _build_synthesis)
    graph.add_node("persist_state", _persist_state)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "classify_intent")
    graph.add_edge("classify_intent", "dispatch_tools")
    graph.add_edge("dispatch_tools", "build_synthesis")
    graph.add_edge("build_synthesis", "persist_state")
    graph.add_edge("persist_state", END)

    _tutor_graph = graph.compile()
    _logger.info("[Tutor] TutorOrchestrator graph compiled")
    return _tutor_graph
