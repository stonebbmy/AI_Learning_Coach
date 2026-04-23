"""
聊天缓存模块：精确缓存（Redis）+ 语义缓存（Chroma）双层架构，并内置命中率监控。

缓存分层策略（面试考点）：
- 第一层：精确缓存（Redis）
  原理：对归一化后的问题做 SHA256，存入 Redis，完全匹配才命中
  适用：相同问题重复问，完全消除 LLM 调用
  TTL：由 CHAT_CACHE_TTL_SECONDS 控制（默认 1 小时）

- 第二层：语义缓存（Chroma 向量相似度）
  原理：对问题做 embedding，在向量库中查找语义相近的历史问题
  适用：「深度学习怎么学」和「如何入门深度学习」应该返回相同答案
  阈值：SEMANTIC_CACHE_MAX_DISTANCE 控制精度（越小越严格）

命中率监控：
- 每次缓存查询后调用 metrics.record_*_cache_hit() 写入 Redis 计数器
- /api/metrics/stats 端点实时读取并计算命中率
- 生产中应该 target exact hit rate > 30%, semantic hit rate > 10%
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

from langchain.schema.document import Document

from ..core.config import settings
from ..core.trace import get_request_id
from ..rag.vector_store import get_semantic_cache_store
from .redis_client import get_redis
from ..api.metrics import record_exact_cache_hit, record_semantic_cache_hit


def normalize_question(text: str) -> str:
    return " ".join(text.strip().lower().split())


def exact_cache_key(question: str) -> str:
    h = hashlib.sha256(normalize_question(question).encode("utf-8")).hexdigest()
    return f"cache:chat:exact:{h}"


def get_exact_cached_answer(question: str) -> Optional[str]:
    r = get_redis()
    if not r:
        return None
    try:
        raw = r.get(exact_cache_key(question))
        if not raw:
            record_exact_cache_hit(False)
            return None
        data = json.loads(raw)
        answer = str(data.get("answer", "")) or None
        record_exact_cache_hit(bool(answer))
        return answer
    except Exception as e:
        print(f"[rid={get_request_id()}] exact cache read failed: {e}")
        return None


def set_exact_cached_answer(question: str, answer: str) -> None:
    r = get_redis()
    if not r:
        return
    try:
        r.setex(
            exact_cache_key(question),
            settings.CHAT_CACHE_TTL_SECONDS,
            json.dumps({"answer": answer}, ensure_ascii=False),
        )
    except Exception as e:
        print(f"[rid={get_request_id()}] exact cache write failed: {e}")


def try_semantic_cache_hit(question: str) -> Optional[str]:
    """Chroma 语义相似缓存：问题 embedding 近邻命中则返回答案。"""
    if not settings.SEMANTIC_CACHE_ENABLED:
        return None
    try:
        store = get_semantic_cache_store()
        pairs = store.similarity_search_with_score(question, k=1)
        if not pairs:
            record_semantic_cache_hit(False)
            return None
        doc, dist = pairs[0]
        # Chroma 默认多为 L2；距离越小越相似
        if float(dist) > settings.SEMANTIC_CACHE_MAX_DISTANCE:
            record_semantic_cache_hit(False)
            return None
        ans = doc.metadata.get("answer")
        hit = bool(ans)
        if hit:
            print(f"[rid={get_request_id()}] semantic cache hit dist={dist:.4f}")
        record_semantic_cache_hit(hit)
        return str(ans) if ans else None
    except Exception as e:
        print(f"[rid={get_request_id()}] semantic cache lookup failed: {e}")
        return None


def add_semantic_cache_entry(question: str, answer: str) -> None:
    if not settings.SEMANTIC_CACHE_ENABLED:
        return
    try:
        store = get_semantic_cache_store()
        norm = normalize_question(question)
        doc = Document(
            page_content=norm,
            metadata={"answer": answer, "original_question": question[:2000]},
        )
        store.add_documents([doc])
    except Exception as e:
        print(f"[rid={get_request_id()}] semantic cache write failed: {e}")
