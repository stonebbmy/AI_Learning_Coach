from __future__ import annotations

from langchain.schema.document import Document

from ..core.config import settings
from ..core.trace import get_request_id
from ..rag.vector_store import get_session_memory_store


def retrieve_long_memory_context(session_id: str, question: str) -> str:
    """
    长期记忆：从独立 Chroma collection 中按 session_id 元数据 + 问题相似度检索历史片段。
    类比：给会话单独建了一个「小 ES 索引」，专存历史摘要/问答对。
    """
    if not settings.LONG_MEMORY_ENABLED or not session_id:
        return ""
    try:
        store = get_session_memory_store()
        docs = store.similarity_search(
            question,
            k=3,
            filter={"session_id": session_id},
        )
        if not docs:
            return ""
        parts = []
        for d in docs:
            parts.append(d.page_content.strip())
        return "\n---\n".join(parts)[: settings.CHAT_HISTORY_MAX_CHARS]
    except TypeError:
        # 旧版 chroma/langchain 可能不支持 filter，退化为无过滤检索
        try:
            store = get_session_memory_store()
            docs = store.similarity_search(question, k=5)
            filtered = [d for d in docs if d.metadata.get("session_id") == session_id][:3]
            if not filtered:
                return ""
            return "\n---\n".join(d.page_content for d in filtered)[
                : settings.CHAT_HISTORY_MAX_CHARS
            ]
        except Exception as e:
            print(f"[rid={get_request_id()}] long memory fallback failed: {e}")
            return ""
    except Exception as e:
        print(f"[rid={get_request_id()}] long memory retrieve failed: {e}")
        return ""


def index_qa_turn(session_id: str, question: str, answer: str) -> None:
    """将一轮问答写入长期记忆向量库（可异步/批量优化；MVP 同步写入）。"""
    if not settings.LONG_MEMORY_ENABLED or not session_id:
        return
    try:
        store = get_session_memory_store()
        text = f"Q: {question}\nA: {answer[:1500]}"
        doc = Document(
            page_content=text,
            metadata={"session_id": session_id},
        )
        store.add_documents([doc])
    except Exception as e:
        print(f"[rid={get_request_id()}] long memory index failed: {e}")
