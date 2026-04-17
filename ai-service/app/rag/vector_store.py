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

_vector_store = None

def get_vector_store() -> Chroma:
    """
    获取或创建一个全局的 Chroma 向量数据库实例 (单例模式)。
    
    使用持久化客户端，确保数据在服务重启后依然存在。

    Returns:
        Chroma: 向量数据库实例。
    """
    global _vector_store
    if _vector_store is None:
        # 统一 Chroma 拓扑：默认连接 docker-compose 的 chroma server
        if settings.CHROMA_MODE.lower() == "remote":
            client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            mode_desc = f"remote({settings.CHROMA_HOST}:{settings.CHROMA_PORT})"
        else:
            client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
            mode_desc = f"embedded({settings.CHROMA_DB_PATH})"

        _vector_store = Chroma(
            client=client,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
        )
        print(f"Chroma vector store initialized: {mode_desc}")
    return _vector_store

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

