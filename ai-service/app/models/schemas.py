
from pydantic import BaseModel, Field
from typing import List, Optional

# ==========================================================================
# 基础模型
# ==========================================================================

class StatusResponse(BaseModel):
    """通用状态响应模型"""
    success: bool
    message: str

# ==========================================================================
# /outline/generate - 大纲生成
# ==========================================================================

class OutlineGenerateRequest(BaseModel):
    """生成学习大纲的请求体"""
    target: str = Field(..., description="学习目标，例如：'成为一名能在3个月内独立开发AI应用的Java工程师'", min_length=10)
    deadline: str = Field(..., description="截止日期，例如：'3个月'", min_length=1)

class StudyChapter(BaseModel):
    """学习大纲中的章节"""
    chapter_title: str = Field(..., description="章节标题")
    description: str = Field(..., description="本章学习内容的简要描述")
    key_points: List[str] = Field(..., description="本章需要掌握的关键知识点列表")

class StudyOutlineResponse(BaseModel):
    """结构化的学习大纲响应模型 (用于 PydanticOutputParser)"""
    title: str = Field(..., description="整个学习计划的总标题")
    overview: str = Field(..., description="对整个学习计划的总体概述和建议")
    chapters: List[StudyChapter] = Field(..., description="学习章节列表")

# ==========================================================================
# /plan/daily - 每日计划
# ==========================================================================

class DailyPlanRequest(BaseModel):
    """生成每日计划的请求体"""
    goal: str = Field(..., description="今天的核心学习目标，例如：'学习并实践 LangChain 的 LCEL'")

class Task(BaseModel):
    """每日计划中的单个任务"""
    task_id: int = Field(..., description="任务序号")
    description: str = Field(..., description="任务的具体内容")
    estimated_time: str = Field(..., description="预计花费时间，例如 '1-2 小时'")
    status: str = Field("待开始", description="任务状态")

class DailyPlanResponse(BaseModel):
    """每日计划的响应体"""
    plan_title: str = Field(..., description="每日计划的标题")
    tasks: List[Task] = Field(..., description="任务列表")

# ==========================================================================
# /chat - RAG 问答
# ==========================================================================

class ChatMessage(BaseModel):
    """单条对话消息（短期记忆由服务端 Redis 与会话 ID 维护；也可由客户端显式传入）。"""
    role: str = Field(..., description="user 或 assistant")
    content: str = Field(..., description="消息正文")


class ChatRequest(BaseModel):
    """问答请求体"""
    question: str = Field(..., description="用户提出的问题")
    session_id: str = Field("default_session", description="会话ID，用于跟踪对话历史")
    messages: List[ChatMessage] = Field(default_factory=list, description="可选：客户端携带的近期多轮消息")


class ChatAgentRequest(BaseModel):
    """工具调用 Agent 问答（非流式）"""
    question: str = Field(..., description="用户问题")
    session_id: str = Field("default_session", description="会话 ID（日志关联）")

# ChatResponse 不是一个 Pydantic 模型, 因为它是一个流式响应。
# 数据将通过服务器发送事件 (Server-Sent Events) 发送。

# ==========================================================================
# /knowledge/upload - 知识库上传
# ==========================================================================

# 此端点的请求将是 FastAPI 的 `UploadFile`, 而不是 Pydantic 模型。
# 响应将是 `StatusResponse`。


class KnowledgeSourceItem(BaseModel):
    """按源文件聚合后的知识库条目"""
    source: str = Field(..., description="Markdown 文件名")
    chunk_count: int = Field(..., description="该文件切分后的向量块数量")
    upload_date: Optional[str] = Field(None, description="上传日期（来自元数据）")


class KnowledgeSummaryResponse(BaseModel):
    """知识库概览：总块数 + 按文件统计"""
    total_chunks: int
    sources: List[KnowledgeSourceItem]


class KnowledgeChunkItem(BaseModel):
    """单条向量块（用于浏览，正文为截断预览）"""
    id: str
    source: Optional[str] = None
    upload_date: Optional[str] = None
    text_preview: str = Field(..., description="正文预览（截断）")
    text_length: int = Field(..., description="原始正文长度")


class KnowledgeChunksResponse(BaseModel):
    """分页拉取向量块"""
    limit: int
    offset: int
    has_more: bool
    chunks: List[KnowledgeChunkItem]

