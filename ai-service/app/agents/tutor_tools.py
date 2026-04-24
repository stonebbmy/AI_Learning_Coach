"""
智能私教编排器的工具函数库。

设计原则：
- 每个工具都是独立的 async 函数，允许 asyncio.gather 并行执行
- 复用现有组件（qa_chain、planner_graph、search_my_notes、conversation memory）
- 工具内部做降级处理，失败时返回空字符串/空列表，不向上抛出
- 统一超时：外层 asyncio.wait_for 兜底，内部各工具设自己的 timeout
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ..core.config import settings
from ..core.llm import ainvoke_with_retry, llm_for_structured
from ..core.trace import get_request_id

_logger = logging.getLogger(__name__)

# ── 工具超时配置（秒）────────────────────────────────────────────────────────
_RAG_TIMEOUT = 30.0
_NOTES_TIMEOUT = 10.0
_WEB_TIMEOUT = 20.0
_QUIZ_TIMEOUT = 25.0
_REVIEW_TIMEOUT = 15.0
_LLM_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# 工具 1：RAG 问答（复用 get_qa_chain）
# ---------------------------------------------------------------------------

async def tool_rag_answer(
    question: str,
    history_block: str = "",
    user_id: str = "anonymous",
) -> str:
    """基于知识库的 RAG 问答。复用现有 get_qa_chain。"""
    try:
        from ..agents.qa import get_qa_chain
        chain = get_qa_chain()
        result = await asyncio.wait_for(
            chain.ainvoke({"question": question, "history_block": history_block}),
            timeout=_RAG_TIMEOUT,
        )
        return result or ""
    except asyncio.TimeoutError:
        _logger.warning("[TutorTool] rag_answer timeout")
        return ""
    except Exception as e:
        _logger.warning("[TutorTool] rag_answer error: %s", e)
        return ""


# ---------------------------------------------------------------------------
# 工具 2：知识库笔记检索（复用 search_my_notes，无 @tool 装饰器）
# ---------------------------------------------------------------------------

async def tool_search_knowledge(query: str, user_id: str = "anonymous") -> str:
    """在个人知识库中语义检索相关内容。"""
    try:
        from ..rag.retriever import get_retriever_from_store
        retriever = get_retriever_from_store()
        docs = await asyncio.wait_for(
            asyncio.to_thread(retriever.invoke, query),
            timeout=_NOTES_TIMEOUT,
        )
        if not docs:
            return ""
        parts = [
            f"[来源: {d.metadata.get('source', '未知')}]\n{d.page_content}"
            for d in docs[:5]
        ]
        return "\n\n---\n\n".join(parts)
    except asyncio.TimeoutError:
        _logger.warning("[TutorTool] search_knowledge timeout")
        return ""
    except Exception as e:
        _logger.warning("[TutorTool] search_knowledge error: %s", e)
        return ""


# ---------------------------------------------------------------------------
# 工具 3：联网搜索（复用 mcp_adapter.web_research）
# ---------------------------------------------------------------------------

async def tool_web_research(query: str) -> str:
    """通过 MCP 适配器进行联网信息检索（降级友好）。"""
    try:
        from ..tools.mcp_adapter import web_research
        result = await asyncio.wait_for(
            asyncio.to_thread(web_research, query),
            timeout=_WEB_TIMEOUT,
        )
        return result or ""
    except asyncio.TimeoutError:
        _logger.warning("[TutorTool] web_research timeout")
        return ""
    except Exception as e:
        _logger.warning("[TutorTool] web_research not available: %s", e)
        return ""


# ---------------------------------------------------------------------------
# 工具 4：生成测验题（新增，基于 LLM + 上下文）
# ---------------------------------------------------------------------------

_QUIZ_SYSTEM = """你是一位专业的学习测评专家。根据提供的学习主题和参考内容，生成高质量的测验题。

要求：
1. 生成 3-5 道选择题或简答题，难度适中
2. 每道题必须基于参考内容，不能凭空发挥
3. 输出格式为 JSON 数组，每个对象包含：
   - question: 题目
   - type: "choice" 或 "open"
   - options: 选项列表（仅 choice 类型）
   - answer: 正确答案
   - explanation: 解析说明

只输出 JSON 数组，不要其他文字。"""


async def tool_generate_quiz(topic: str, context: str) -> List[Dict[str, Any]]:
    """基于当前学习主题和知识内容生成测验题。"""
    if not topic and not context:
        return []
    try:
        prompt_text = f"学习主题：{topic}\n\n参考内容：\n{context[:3000]}"
        messages = [
            SystemMessage(content=_QUIZ_SYSTEM),
            HumanMessage(content=prompt_text),
        ]
        resp = await asyncio.wait_for(
            llm_for_structured.ainvoke(messages),
            timeout=_QUIZ_TIMEOUT,
        )
        text = resp.content.strip()
        # 提取 JSON 数组
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        questions = json.loads(text)
        if isinstance(questions, list):
            return questions[:5]
        return []
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
        _logger.warning("[TutorTool] generate_quiz error: %s", e)
        return []


# ---------------------------------------------------------------------------
# 工具 5：间隔复习（基于长期记忆向量检索）
# ---------------------------------------------------------------------------

async def tool_spaced_review(
    user_id: str,
    session_id: str,
    topic: str = "",
) -> str:
    """
    基于艾宾浩斯遗忘曲线的间隔复习。
    从 ChromaDB 长期记忆中检索需要复习的历史内容。
    """
    try:
        from ..rag.retriever import get_retriever_from_store
        query = f"复习 {topic}" if topic else "之前学习的重要知识点"
        retriever = get_retriever_from_store()
        docs = await asyncio.wait_for(
            asyncio.to_thread(retriever.invoke, query),
            timeout=_REVIEW_TIMEOUT,
        )
        if not docs:
            return ""
        review_parts = []
        for doc in docs[:4]:
            src = doc.metadata.get("source", "笔记")
            review_parts.append(f"【{src}】\n{doc.page_content[:500]}")
        return "\n\n".join(review_parts)
    except asyncio.TimeoutError:
        _logger.warning("[TutorTool] spaced_review timeout")
        return ""
    except Exception as e:
        _logger.warning("[TutorTool] spaced_review error: %s", e)
        return ""


# ---------------------------------------------------------------------------
# 工具 6：获取当日计划（通过 planner_graph 或 Redis 缓存）
# ---------------------------------------------------------------------------

async def tool_get_plan_context(
    plan_tasks: List[Dict[str, Any]],
    outline_chapters: List[str],
) -> str:
    """将已加载的计划数据格式化为可读字符串（不重复调用 LLM）。"""
    if not plan_tasks:
        return ""
    pending = [t for t in plan_tasks if t.get("status") not in ("done", "completed", "DONE")]
    done = [t for t in plan_tasks if t.get("status") in ("done", "completed", "DONE")]
    parts = []
    if done:
        parts.append(f"✅ 已完成 {len(done)} 个任务")
    if pending:
        pending_desc = "、".join(
            t.get("description", t.get("name", "任务")) for t in pending[:3]
        )
        parts.append(f"📋 待完成：{pending_desc}")
    total = len(plan_tasks)
    done_count = len(done)
    parts.append(f"进度：{done_count}/{total}")
    return "；".join(parts)


# ---------------------------------------------------------------------------
# 工具 7：Redis 中获取 Tutor 上下文状态
# ---------------------------------------------------------------------------

def load_tutor_context(user_id: str) -> Dict[str, Any]:
    """从 Redis 读取 tutor:ctx:{user_id} Hash，返回字典。"""
    try:
        from ..cache.redis_client import get_redis
        r = get_redis()
        if not r:
            return {}
        key = f"tutor:ctx:{user_id}"
        raw = r.hgetall(key)
        if not raw:
            return {}
        result: Dict[str, Any] = {}
        for k, v in raw.items():
            if k in ("current_outline_id", "current_plan_id"):
                result[k] = int(v) if v and v != "None" else None
            elif k == "progress_rate":
                result[k] = float(v) if v else 0.0
            elif k in ("outline_chapters", "plan_tasks"):
                try:
                    result[k] = json.loads(v)
                except Exception:
                    result[k] = []
            else:
                result[k] = v
        return result
    except Exception as e:
        _logger.warning("[TutorTool] load_tutor_context error: %s", e)
        return {}


def save_tutor_context(user_id: str, ctx: Dict[str, Any], ttl_seconds: int = 0) -> None:
    """将 tutor:ctx:{user_id} 写入 Redis Hash，默认 TTL 来自 settings.TUTOR_CTX_TTL_SECONDS（7天）。"""
    if ttl_seconds <= 0:
        ttl_seconds = settings.TUTOR_CTX_TTL_SECONDS
    try:
        from ..cache.redis_client import get_redis
        r = get_redis()
        if not r:
            return
        key = f"tutor:ctx:{user_id}"
        mapping: Dict[str, str] = {}
        for k, v in ctx.items():
            if isinstance(v, (list, dict)):
                mapping[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                mapping[k] = "None"
            else:
                mapping[k] = str(v)
        if mapping:
            r.hset(key, mapping=mapping)
            r.expire(key, ttl_seconds)
    except Exception as e:
        _logger.warning("[TutorTool] save_tutor_context error: %s", e)
