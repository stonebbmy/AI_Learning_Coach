"""
LangGraph 每日学习计划生成图。

高可用改造（vs 原版）：
- _draft_plan / _repair_plan 的 LLM 调用替换为 ainvoke_with_retry
  → 自动享有：熔断检查 + 指数退避重试 + 单次调用超时
- _validate_plan 增加 markdown 代码块剥离（LLM 有时会输出 ```json ... ```）
- plan.py（调用层）用 asyncio.wait_for 控制整图总超时
"""

from __future__ import annotations

import json
from typing import Any, Dict, TypedDict

from langgraph.graph import END, StateGraph
from langchain.prompts import ChatPromptTemplate

from ..core.llm import ainvoke_with_retry
from ..models.schemas import DailyPlanResponse
from ..tools.local_tools import search_my_notes
from ..tools.mcp_adapter import web_research
from ..core.trace import get_request_id
from ..core.config import settings


class PlannerState(TypedDict, total=False):
    goal: str
    notes_context: str
    web_context: str
    plan_raw: str
    plan: Dict[str, Any]
    validation_error: str
    repair_count: int


_planner_graph = None


def get_planner_graph():
    global _planner_graph
    if _planner_graph is None:
        _planner_graph = _build_planner_graph()
    return _planner_graph


def _build_planner_graph():
    graph = StateGraph(PlannerState)

    graph.add_node("analyze_goal", _analyze_goal)
    graph.add_node("retrieve_notes", _retrieve_notes)
    graph.add_node("web_research", _web_research_node)
    graph.add_node("draft_plan", _draft_plan)
    graph.add_node("validate_plan", _validate_plan)
    graph.add_node("repair_plan", _repair_plan)

    graph.set_entry_point("analyze_goal")
    graph.add_edge("analyze_goal", "retrieve_notes")
    graph.add_edge("retrieve_notes", "web_research")
    graph.add_edge("web_research", "draft_plan")
    graph.add_edge("draft_plan", "validate_plan")

    graph.add_conditional_edges(
        "validate_plan",
        _route_after_validation,
        {"ok": END, "repair": "repair_plan"},
    )
    graph.add_edge("repair_plan", "validate_plan")

    return graph.compile()


# ---------------------------------------------------------------------------
# 节点实现
# ---------------------------------------------------------------------------

async def _analyze_goal(state: PlannerState) -> PlannerState:
    """初始化状态，可扩展为决策节点（是否联网/检索）。"""
    print(f"[rid={get_request_id()}] planner.analyze_goal: {state.get('goal', '')[:50]}")
    return {"repair_count": 0}


async def _retrieve_notes(state: PlannerState) -> PlannerState:
    """从本地知识库检索与目标相关的笔记。"""
    goal = state["goal"]
    print(f"[rid={get_request_id()}] planner.retrieve_notes")
    notes_context = search_my_notes.invoke({"query": goal})
    return {"notes_context": notes_context}


async def _web_research_node(state: PlannerState) -> PlannerState:
    """通过 MCP web_search 联网检索补充信息。失败时降级为空字符串，不中断流程。"""
    print(f"[rid={get_request_id()}] planner.web_research")
    try:
        ctx = await web_research(state["goal"])
    except Exception as e:
        print(f"[rid={get_request_id()}] planner.web_research failed (degraded): {e}")
        ctx = ""
    return {"web_context": ctx}


_DRAFT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是一个高效的个人学习计划制定助理。
你的任务是根据用户今天的主要目标，结合提供的上下文，为用户生成一份具体、可执行的任务清单。

强约束：你的输出必须是一个"可被 JSON 解析"的对象字符串，且只输出 JSON，不要输出任何额外文本。

JSON schema:
{{
  "plan_title": "string",
  "tasks": [
    {{
      "task_id": 1,
      "description": "string",
      "estimated_time": "string",
      "status": "待开始"
    }}
  ]
}}

要求：
1) 任务数 3-5 个
2) 任务粒度可执行（包含动作、产出物）
3) estimated_time 给出区间（例如 30-45分钟 / 1-2小时）
""".strip(),
        ),
        ("human", "今天目标：{goal}\n\n【我的笔记检索上下文】\n{notes_context}\n\n【联网检索上下文】\n{web_context}"),
    ]
)


async def _draft_plan(state: PlannerState) -> PlannerState:
    """
    生成计划草稿。
    使用 ainvoke_with_retry 替代裸 llm.ainvoke，享有：
    - 熔断器保护（LLM 持续故障时快速失败）
    - 指数退避重试（429/5xx 自动重试）
    - 单次超时（LLM_INVOKE_TIMEOUT 秒）
    """
    print(f"[rid={get_request_id()}] planner.draft_plan")
    prompt = _DRAFT_PROMPT.format_messages(
        goal=state["goal"],
        notes_context=state.get("notes_context", ""),
        web_context=state.get("web_context", ""),
    )
    msg = await ainvoke_with_retry(prompt, timeout=settings.LLM_INVOKE_TIMEOUT)
    return {"plan_raw": msg.content}


async def _validate_plan(state: PlannerState) -> PlannerState:
    """
    校验 LLM 输出的 JSON 是否符合 DailyPlanResponse Schema。
    额外处理：剥离 LLM 有时会包裹的 markdown 代码块（``` json ... ```）。
    """
    raw = (state.get("plan_raw") or "").strip()

    # 剥离 markdown 代码块
    if raw.startswith("```"):
        lines = raw.split("\n")
        # 去掉首行（```json 或 ```）和末行（```）
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        raw = "\n".join(inner).strip()

    try:
        data = json.loads(raw)
        DailyPlanResponse(**data)  # Pydantic 字段/类型校验
        return {"plan": data, "validation_error": ""}
    except Exception as e:
        print(f"[rid={get_request_id()}] planner.validate_plan failed: {e}")
        return {"validation_error": str(e)}


def _route_after_validation(state: PlannerState) -> str:
    """条件边路由函数：验证通过则结束，失败且未超限则进修复节点。"""
    if not state.get("validation_error"):
        return "ok"
    if (state.get("repair_count") or 0) >= 2:
        # 超过修复次数上限，强制结束防止无限循环（API 层统一报错）
        print(f"[rid={get_request_id()}] planner: repair limit reached, forcing end")
        return "ok"
    return "repair"


_REPAIR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是一个 JSON 修复器。你会收到一个"应当符合 schema 的 JSON 文本"和一个"校验错误信息"。
你的任务：返回一个修复后的 JSON，对象结构必须满足 schema，且只能输出 JSON 本身（不要解释）。
schema 同 draft 阶段一致：plan_title + tasks[task_id,description,estimated_time,status]，tasks 3-5 个。
""".strip(),
        ),
        ("human", "原始输出：\n{plan_raw}\n\n校验错误：\n{validation_error}"),
    ]
)


async def _repair_plan(state: PlannerState) -> PlannerState:
    """修复不合规的 JSON。同样使用 ainvoke_with_retry 保护。"""
    attempt = (state.get("repair_count") or 0) + 1
    print(f"[rid={get_request_id()}] planner.repair_plan (attempt {attempt})")
    prompt = _REPAIR_PROMPT.format_messages(
        plan_raw=state.get("plan_raw", ""),
        validation_error=state.get("validation_error", ""),
    )
    msg = await ainvoke_with_retry(prompt, timeout=settings.LLM_INVOKE_TIMEOUT)
    return {
        "plan_raw": msg.content,
        "repair_count": attempt,
    }
