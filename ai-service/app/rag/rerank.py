"""
检索后重排序（面试点：两阶段检索 —— 召回宽、排序严）。

本实现使用「与向量库相同的 Embedding」对候选文档做余弦相似度打分，再取 Top-N。
类比 Java：在 ES 粗排后接一层 Learning-to-Rank 或业务规则重排；此处用向量相似度代替 Cross-Encoder，避免额外大依赖。
"""

from __future__ import annotations

from typing import List

import numpy as np
from langchain.schema.document import Document

from ..core.config import settings
from ..core.llm import embeddings


def rerank_documents_by_embedding(query: str, docs: List[Document], top_n: int | None = None) -> List[Document]:
    """对候选文档按与 query 的 embedding 余弦相似度重排，返回 Top-N。"""
    if not docs:
        return []
    n = top_n if top_n is not None else settings.RERANK_TOP_N
    if len(docs) <= n and not settings.RERANK_ENABLED:
        return docs

    q = np.asarray(embeddings.embed_query(query), dtype=np.float64)
    q_norm = np.linalg.norm(q) + 1e-9
    texts = [d.page_content for d in docs]
    mat = np.asarray(embeddings.embed_documents(texts), dtype=np.float64)
    norms = np.linalg.norm(mat, axis=1) + 1e-9
    sims = (mat @ q) / (norms * q_norm)
    order = np.argsort(-sims)
    seen = set()
    out: List[Document] = []
    for i in order:
        idx = int(i)
        key = id(docs[idx])
        if key in seen:
            continue
        seen.add(key)
        out.append(docs[idx])
        if len(out) >= n:
            break
    return out
