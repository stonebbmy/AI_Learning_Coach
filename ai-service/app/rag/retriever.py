
from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain.schema import Document
from .vector_store import get_vector_store


def get_retriever_from_store() -> EnsembleRetriever:
    """
    从持久化的向量数据库中创建并返回一个混合检索器 (EnsembleRetriever)。
    该检索器用于实时问答，会从整个知识库中进行检索。

    Returns:
        EnsembleRetriever: 结合了 BM25 和向量检索的混合检索器。
    """
    print("Initializing retriever from existing vector store...")
    vector_store = get_vector_store()

    # 1. 从 ChromaDB 中获取所有已存在的文档块
    # BM25Retriever 需要 Document 对象列表来进行初始化，所以我们必须取出所有数据。
    # 注意：对于非常大的知识库，这可能会有性能问题。但在MVP阶段是可接受的。
    existing_docs = vector_store.get(include=["metadatas", "documents"])
    
    if not existing_docs or not existing_docs.get('ids'):
        print("Vector store is empty. Returning a base vector retriever.")
        # 如果数据库为空，返回一个基础的向量检索器以避免错误
        return vector_store.as_retriever(search_kwargs={"k": 1})

    # 将从 ChromaDB 取出的原始数据重新构建为 LangChain 的 Document 对象
    reconstructed_docs = [
        Document(page_content=doc, metadata=meta)
        for doc, meta in zip(existing_docs['documents'], existing_docs['metadatas'])
    ]
    print(f"Reconstructed {len(reconstructed_docs)} documents for BM25 retriever.")

    # 2. 初始化 BM25 检索器 (关键字检索)
    bm25_retriever = BM25Retriever.from_documents(reconstructed_docs)
    bm25_retriever.k = 3 # 设置返回最相关的3个结果

    # 3. 初始化向量存储检索器 (语义检索)
    vector_retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    # 4. 初始化混合检索器 (EnsembleRetriever)
    # 按照要求，设置权重为 向量:BM25 = 7:3
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.3, 0.7]
    )
    
    print("Ensemble retriever initialized successfully.")
    return ensemble_retriever

