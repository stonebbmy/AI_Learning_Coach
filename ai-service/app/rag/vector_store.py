import sys

# Chroma 依赖 sqlite3 >= 3.35，但 Debian bullseye 的系统 sqlite3 偏旧。
# 优先使用 pysqlite3-binary 提供的新版 sqlite3 实现来满足运行时要求。
try:
    import pysqlite3  # type: ignore
    sys.modules["sqlite3"] = pysqlite3
except Exception:
    pass

import chromadb
from langchain_community.vectorstores import Chroma
from typing import List
from langchain.schema.document import Document

from ..core.config import settings
from ..core.llm import embeddings

_chroma_client = None
_chroma_stores: dict[str, Chroma] = {}


def get_chroma_client():
    """单一 Chroma 客户端（remote 或 embedded），供多个 collection 复用。"""
    global _chroma_client
    if _chroma_client is None:
        if settings.CHROMA_MODE.lower() == "remote":
            _chroma_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            mode_desc = f"remote({settings.CHROMA_HOST}:{settings.CHROMA_PORT})"
        else:
            _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
            mode_desc = f"embedded({settings.CHROMA_DB_PATH})"
        print(f"Chroma client initialized: {mode_desc}")
    return _chroma_client


def get_chroma_collection(collection_name: str) -> Chroma:
    """按集合名获取 LangChain Chroma 封装（多 collection 单例）。"""
    if collection_name not in _chroma_stores:
        _chroma_stores[collection_name] = Chroma(
            client=get_chroma_client(),
            collection_name=collection_name,
            embedding_function=embeddings,
        )
        print(f"Chroma collection ready: {collection_name}")
    return _chroma_stores[collection_name]


def get_vector_store() -> Chroma:
    """
    获取笔记知识库向量集合（默认 ai_learning_notes）。
    """
    return get_chroma_collection(settings.CHROMA_COLLECTION_NAME)


def get_semantic_cache_store() -> Chroma:
    """语义相似问答缓存（与笔记库隔离的 collection）。"""
    return get_chroma_collection(settings.SEMANTIC_CACHE_COLLECTION)


def get_session_memory_store() -> Chroma:
    """长期会话记忆：按 session 元数据过滤检索历史问答片段。"""
    return get_chroma_collection(settings.SESSION_MEMORY_COLLECTION)


def add_documents_to_store(documents: List[Document]):
    """
    将文档块添加到向量数据库中。

    Args:
        documents (List[Document]): 经过分割和处理的文档块列表。
    """
    vector_store = get_vector_store()
    if not documents:
        print("No documents to add.")
        return
        
    vector_store.add_documents(documents)
    print(f"Successfully added {len(documents)} document chunks to Chroma collection '{settings.CHROMA_COLLECTION_NAME}'.")
