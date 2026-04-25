"""
智能私教总控层的数据模型定义。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LangGraph 内部状态（TypedDict）
# ---------------------------------------------------------------------------

class TutorState(TypedDict, total=False):
    """编排图的完整状态对象，在节点间共享传递。"""

    # ── 请求信息（入参）──────────────────────────────────────────────────────
    user_id: str
    session_id: str
    user_message: str

    # ── 用户上下文（load_context 节点填充）──────────────────────────────────
    current_outline_id: Optional[int]   # 用户正在学习的大纲 ID
    current_plan_id: Optional[int]      # 今日计划 ID
    active_topic: str                    # 当前活跃章节/主题
    progress_rate: float                 # 总体任务完成率 [0, 1]
    outline_chapters: List[str]          # 大纲章节标题列表
    plan_tasks: List[Dict[str, Any]]     # 今日任务列表（taskId/description/status）
    chat_history: List[Dict[str, str]]   # 短期对话记忆

    # ── 意图分类（classify_intent 节点填充）─────────────────────────────────
    # ONBOARD | PLAN | LEARN | REVIEW | PROGRESS | QUIZ | EXPLORE
    intent: str
    sub_tasks: List[str]   # 本轮需要调用的工具名称列表

    # ── 工具结果（dispatch_tools 节点填充）──────────────────────────────────
    notes_context: str       # 知识库检索结果
    rag_answer: str          # RAG 问答结果
    web_context: str         # MCP 联网检索结果
    progress_summary: Dict[str, Any]   # 进度汇总
    quiz_questions: List[Dict[str, Any]]  # 生成的测验题
    review_items: str        # 间隔复习内容

    # ── 三层历史上下文（load_context 节点填充）──────────────────────────────
    rich_history: str        # 分层组装的历史 block（摘要+长期记忆+近期窗口）

    # ── ONBOARD 工具结果（dispatch_tools 节点填充）──────────────────────────
    generated_outline: Optional[dict]  # ONBOARD 意图生成的大纲数据（供前端卡片展示）

    # ── 合成输出（build_synthesis 节点填充）─────────────────────────────────
    synthesis_prompt: str    # 传给最终 LLM 的合成 Prompt
    tutor_actions: List[str] # 执行了哪些动作（前端展示用）


# ---------------------------------------------------------------------------
# API Request / Response（Pydantic）
# ---------------------------------------------------------------------------

class TutorRequest(BaseModel):
    """客户端发送给 /api/tutor/chat 的请求体。"""

    question: str = Field(..., description="用户自然语言输入", min_length=1)
    session_id: str = Field("tutor_default", description="会话 ID，用于多轮记忆")
    user_id: str = Field("anonymous", description="用户唯一标识")


class IntentResult(BaseModel):
    """意图分类的 JSON 输出结构（用于 LLM 结构化输出）。"""

    intent: str = Field(
        ...,
        description="意图类别：ONBOARD / PLAN / LEARN / REVIEW / PROGRESS / QUIZ / EXPLORE",
    )
    sub_tasks: List[str] = Field(
        default_factory=list,
        description="需要调用的工具名称列表",
    )
    reason: str = Field("", description="分类理由（调试用）")
