from __future__ import annotations

import hashlib
import json
from typing import Optional

from langchain.schema.document import Document

from ..core.config import settings
from ..core.trace import get_request_id
from ..rag.vector_store import get_semantic_cache_store
from .redis_client import get_redis


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
            return None
        data = json.loads(raw)
        return str(data.get("answer", "")) or None
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
            return None
        doc, dist = pairs[0]
        # Chroma 默认多为 L2；距离越小越相似
        if float(dist) > settings.SEMANTIC_CACHE_MAX_DISTANCE:
            return None
        ans = doc.metadata.get("answer")
        if ans:
            print(f"[rid={get_request_id()}] semantic cache hit dist={dist:.4f}")
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
