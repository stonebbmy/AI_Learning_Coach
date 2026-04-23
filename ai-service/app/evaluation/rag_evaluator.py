"""
RAG 质量评估模块（LLM-as-Judge 模式）。

面试核心考点：
Q: 如何评估 RAG 系统的质量？
A: 三个关键维度（RAGAS 框架启发）：
   1. 忠实度（Faithfulness）：答案是否完全基于检索到的上下文，不幻觉
   2. 答案相关性（Answer Relevance）：答案是否切中问题
   3. 上下文召回率（Context Recall）：检索到的文档是否覆盖了问题的关键信息

Q: LLM-as-Judge 的优缺点？
A:
   优点：评估质量接近人类判断，不需要大量标注数据，灵活应对新场景
   缺点：评估本身有 LLM 调用成本，Judge LLM 也有偏置（Position Bias、Self-Enhancement Bias）
   缓解：使用与 RAG 不同的 LLM 做 Judge，多次采样取平均，设置 CoT 推理要求 Judge 给出理由

Q: RAGAS vs 本实现的区别？
A: RAGAS 是完整评估框架，有自己的数据集管理和多种评估指标；
   本实现是轻量内嵌版，适合在 API 端点上做实时/按需评估，无额外依赖。

生产部署建议：
- 不在正常请求链路中做评估（增加延迟）
- 离线采样 5-10% 的请求进行评估（异步 Job）
- 将评估结果写入 PostgreSQL，用 Grafana 绘制质量趋势图
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter
# langchain_core.messages 是 LangChain 0.2.x 正确的消息导入路径
from langchain_core.messages import HumanMessage

from ..core.llm import llm
from ..agents.qa import get_qa_chain, retrieve_and_format_docs

router = APIRouter()


@dataclass
class RAGEvalResult:
    """单次 RAG 评估结果。"""
    question: str
    context: str
    answer: str
    faithfulness_score: float       # 0-1，答案是否完全基于上下文
    answer_relevance_score: float   # 0-1，答案是否切中问题
    context_relevance_score: float  # 0-1，上下文是否与问题相关
    overall_score: float            # 综合分（三项均值）
    faithfulness_reason: str = ""
    answer_relevance_reason: str = ""
    context_relevance_reason: str = ""


# ---------------------------------------------------------------------------
# 评估 Prompt 模板（CoT 要求：先给理由，再给分数）
# ---------------------------------------------------------------------------

_FAITHFULNESS_PROMPT = """
你是一个 RAG 系统质量评估专家。请评估以下答案的"忠实度"：答案是否完全基于给定的上下文，没有引入上下文中不存在的信息（即没有幻觉）。

【上下文】
{context}

【问题】
{question}

【答案】
{answer}

评估标准：
- 1.0：答案完全来自上下文，没有任何凭空捏造的内容
- 0.5：答案大部分基于上下文，但有少量不确定的推断
- 0.0：答案包含上下文中不存在的重要内容（幻觉）

请按如下 JSON 格式输出（只输出 JSON，不要其他文字）：
{{"score": 0.0到1.0的浮点数, "reason": "简要说明判断依据（50字以内）"}}
""".strip()

_ANSWER_RELEVANCE_PROMPT = """
你是一个 RAG 系统质量评估专家。请评估以下答案的"答案相关性"：答案是否直接回应了问题，没有偏题。

【问题】
{question}

【答案】
{answer}

评估标准：
- 1.0：答案完整且直接回答了问题
- 0.5：答案部分回答了问题，但不完整或有偏差
- 0.0：答案基本与问题无关

请按如下 JSON 格式输出（只输出 JSON，不要其他文字）：
{{"score": 0.0到1.0的浮点数, "reason": "简要说明判断依据（50字以内）"}}
""".strip()

_CONTEXT_RELEVANCE_PROMPT = """
你是一个 RAG 系统质量评估专家。请评估检索到的"上下文相关性"：上下文是否包含回答问题所需的关键信息。

【问题】
{question}

【上下文】
{context}

评估标准：
- 1.0：上下文包含回答问题所需的所有关键信息
- 0.5：上下文包含部分有用信息，但不够完整
- 0.0：上下文与问题基本无关，无法支撑回答

请按如下 JSON 格式输出（只输出 JSON，不要其他文字）：
{{"score": 0.0到1.0的浮点数, "reason": "简要说明判断依据（50字以内）"}}
""".strip()


async def _llm_score(prompt: str) -> tuple[float, str]:
    """调用 LLM 进行评分，解析 JSON 输出，容错处理。"""
    try:
        msg = HumanMessage(content=prompt)
        response = await llm.ainvoke([msg])
        content = response.content.strip()
        # 去除可能的 markdown 代码块包裹
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
        score = float(data.get("score", 0.5))
        reason = str(data.get("reason", ""))
        return max(0.0, min(1.0, score)), reason
    except Exception as e:
        print(f"[RAGEval] LLM scoring failed: {e}")
        return 0.5, f"评估失败: {e}"


async def evaluate_rag(question: str) -> RAGEvalResult:
    """
    对给定问题执行完整的 RAG 三维评估。

    流程：
    1. 执行 RAG 检索，获取上下文
    2. 执行 RAG 生成，获取答案
    3. 并发调用 LLM Judge 进行三维评分（忠实度、答案相关性、上下文相关性）

    注意：此函数会调用 3 次 LLM（Judge），生产中应异步/采样执行。
    """
    import asyncio

    # 获取检索上下文（使用公开别名，避免引用私有函数）
    context = retrieve_and_format_docs(question)

    # 生成答案
    qa_chain = get_qa_chain()
    answer = await qa_chain.ainvoke({"question": question, "history_block": ""})

    # 并发执行三个评估维度
    faithfulness_prompt = _FAITHFULNESS_PROMPT.format(
        context=context[:2000], question=question, answer=answer
    )
    answer_rel_prompt = _ANSWER_RELEVANCE_PROMPT.format(question=question, answer=answer)
    context_rel_prompt = _CONTEXT_RELEVANCE_PROMPT.format(
        question=question, context=context[:2000]
    )

    (faith_score, faith_reason), (ans_score, ans_reason), (ctx_score, ctx_reason) = (
        await asyncio.gather(
            _llm_score(faithfulness_prompt),
            _llm_score(answer_rel_prompt),
            _llm_score(context_rel_prompt),
        )
    )

    overall = round((faith_score + ans_score + ctx_score) / 3, 4)

    return RAGEvalResult(
        question=question,
        context=context[:500] + ("..." if len(context) > 500 else ""),
        answer=answer,
        faithfulness_score=faith_score,
        answer_relevance_score=ans_score,
        context_relevance_score=ctx_score,
        overall_score=overall,
        faithfulness_reason=faith_reason,
        answer_relevance_reason=ans_reason,
        context_relevance_reason=ctx_reason,
    )


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.post("/eval/rag", summary="RAG 质量评估（LLM-as-Judge）")
async def eval_rag_endpoint(request: dict) -> dict:
    """
    对指定问题执行 RAG 三维质量评估。

    请求体：{"question": "你的问题"}
    返回：忠实度、答案相关性、上下文相关性三个维度的分数及原因。

    ⚠️ 此接口会触发 3 次额外 LLM 调用（评估用），适合测试/QA 使用，勿在生产高频调用。
    """
    question = request.get("question", "").strip()
    if not question:
        return {"error": "question 不能为空"}

    result = await evaluate_rag(question)
    return {
        "question": result.question,
        "answer_preview": result.answer[:300],
        "context_preview": result.context,
        "scores": {
            "faithfulness": {"score": result.faithfulness_score, "reason": result.faithfulness_reason},
            "answer_relevance": {"score": result.answer_relevance_score, "reason": result.answer_relevance_reason},
            "context_relevance": {"score": result.context_relevance_score, "reason": result.context_relevance_reason},
            "overall": result.overall_score,
        },
        "interpretation": _interpret_score(result.overall_score),
    }


def _interpret_score(score: float) -> str:
    if score >= 0.8:
        return "优秀：RAG 系统运行良好"
    elif score >= 0.6:
        return "良好：RAG 基本可用，有改进空间"
    elif score >= 0.4:
        return "一般：建议检查知识库质量或检索参数"
    else:
        return "较差：RAG 效果不佳，需要重点优化"
