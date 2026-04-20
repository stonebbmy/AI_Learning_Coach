"""
最小 ReAct 风格工具调用 Agent（面试点：思考 -> 工具 -> 再生成）。

使用 LangGraph 预置的 `create_react_agent`（与项目中 planner_graph 一致依赖 LangGraph）。
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from ..core.llm import llm
from ..tools.local_tools import get_current_time, search_my_notes

_graph = None


def get_react_graph():
    global _graph
    if _graph is None:
        tools = [get_current_time, search_my_notes]
        _graph = create_react_agent(llm, tools)
    return _graph
