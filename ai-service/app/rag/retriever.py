
from typing import List

from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from .vector_store import get_vector_store


class _EmptyRetriever(BaseRetriever):
    """当知识库为空时的安全检索器：始终返回空结果。"""

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        return []


def get_retriever_from_store(*, candidate_k: int | None = None) -> BaseRetriever:
    """
    从持久化的向量数据库中创建并返回一个混合检索器 (EnsembleRetriever)。
    candidate_k：单路召回条数；两路合并后供后续 Embedding 重排序（见 app/rag/rerank.py）。

    Returns:
        EnsembleRetriever: 结合了 BM25 和向量检索的混合检索器。
    """
    from ..core.config import settings

    k = candidate_k if candidate_k is not None else max(3, settings.RETRIEVAL_CANDIDATES // 2)

    print("Initializing retriever from existing vector store...")
    vector_store = get_vector_store()

    # 1. 从 ChromaDB 中获取所有已存在的文档块
    # BM25Retriever 需要 Document 对象列表来进行初始化，所以我们必须取出所有数据。
    # 注意：对于非常大的知识库，这可能会有性能问题。但在MVP阶段是可接受的。
    existing_docs = vector_store.get(include=["metadatas", "documents"])
    
    if not existing_docs or not existing_docs.get('ids'):
        print("Vector store is empty. Returning an empty retriever.")
        # 如果数据库为空，避免走 embedding（某些 provider 可能不支持 embedding 或配置不完整）
        return _EmptyRetriever()

    # 将从 ChromaDB 取出的原始数据重新构建为 LangChain 的 Document 对象
    reconstructed_docs = [
        Document(page_content=doc, metadata=meta)
        for doc, meta in zip(existing_docs['documents'], existing_docs['metadatas'])
    ]
    print(f"Reconstructed {len(reconstructed_docs)} documents for BM25 retriever.")

    # 2. 初始化 BM25 检索器 (关键字检索)
    bm25_retriever = BM25Retriever.from_documents(reconstructed_docs)
    bm25_retriever.k = k

    # 3. 初始化向量存储检索器 (语义检索)
    vector_retriever = vector_store.as_retriever(search_kwargs={"k": k})

    # 4. 初始化混合检索器 (EnsembleRetriever)
    # 按照要求，设置权重为 向量:BM25 = 7:3
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.3, 0.7]
    )
    
    print("Ensemble retriever initialized successfully.")
    return ensemble_retriever

