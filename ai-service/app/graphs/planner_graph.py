from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langchain.prompts import ChatPromptTemplate

from ..core.llm import llm
from ..models.schemas import DailyPlanResponse
from ..tools.local_tools import search_my_notes
from ..tools.mcp_adapter import web_research
from ..core.trace import get_request_id


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
    graph.add_node("web_research", _web_research_placeholder)
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
        {
            "ok": END,
            "repair": "repair_plan",
        },
    )
    graph.add_edge("repair_plan", "validate_plan")

    return graph.compile()


async def _analyze_goal(state: PlannerState) -> PlannerState:
    # 初期版本：只初始化计数器。后续可扩展为“是否需要检索/联网”的决策节点。
    return {"repair_count": 0}


async def _retrieve_notes(state: PlannerState) -> PlannerState:
    goal = state["goal"]
    # 简化：直接用 goal 作为 query。后续可做 query rewrite。
    print(f"[rid={get_request_id()}] planner.retrieve_notes")
    notes_context = search_my_notes.invoke({"query": goal})
    return {"notes_context": notes_context}


async def _web_research_placeholder(state: PlannerState) -> PlannerState:
    # MCP（联网检索）输出作为补充上下文；如果没有可用结果则为空字符串。
    print(f"[rid={get_request_id()}] planner.web_research")
    ctx = await web_research(state["goal"])
    return {"web_context": ctx}


_DRAFT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是一个高效的个人学习计划制定助理。
你的任务是根据用户今天的主要目标，结合提供的上下文，为用户生成一份具体、可执行的任务清单。

强约束：你的输出必须是一个“可被 JSON 解析”的对象字符串，且只输出 JSON，不要输出任何额外文本。

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
    print(f"[rid={get_request_id()}] planner.draft_plan")
    prompt = _DRAFT_PROMPT.format_messages(
        goal=state["goal"],
        notes_context=state.get("notes_context", ""),
        web_context=state.get("web_context", ""),
    )
    msg = await llm.ainvoke(prompt)
    return {"plan_raw": msg.content}


async def _validate_plan(state: PlannerState) -> PlannerState:
    raw = (state.get("plan_raw") or "").strip()
    try:
        data = json.loads(raw)
        # Pydantic 校验（字段/类型）
        DailyPlanResponse(**data)
        return {"plan": data, "validation_error": ""}
    except Exception as e:
        return {"validation_error": str(e)}


def _route_after_validation(state: PlannerState) -> str:
    if not state.get("validation_error"):
        return "ok"
    if (state.get("repair_count") or 0) >= 2:
        # 兜底：修复次数超限也直接结束，让 API 层统一报错
        return "ok"
    return "repair"


_REPAIR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是一个 JSON 修复器。你会收到一个“应当符合 schema 的 JSON 文本”和一个“校验错误信息”。\n
你的任务：返回一个修复后的 JSON，对象结构必须满足 schema，且只能输出 JSON 本身（不要解释）。\n
schema 同 draft 阶段一致：plan_title + tasks[task_id,description,estimated_time,status]，tasks 3-5 个。\n
""".strip(),
        ),
        ("human", "原始输出：\n{plan_raw}\n\n校验错误：\n{validation_error}"),
    ]
)


async def _repair_plan(state: PlannerState) -> PlannerState:
    prompt = _REPAIR_PROMPT.format_messages(
        plan_raw=state.get("plan_raw", ""),
        validation_error=state.get("validation_error", ""),
    )
    msg = await llm.ainvoke(prompt)
    return {
        "plan_raw": msg.content,
        "repair_count": (state.get("repair_count") or 0) + 1,
    }

