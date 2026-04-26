
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from typing import List, Any, Dict
from langchain.schema.document import Document

from ..rag.retriever import get_retriever_from_store
from ..prompts.yaml_loader import build_qa_chat_template
from ..core.llm import llm
from ..core.config import settings
from ..rag.rerank import rerank_documents_by_embedding


def _format_docs(docs: List[Document]) -> str:
    """
    一个辅助函数，将检索到的文档列表格式化为单个字符串，用作 RAG 的上下文。
    同时，它会提取并附加来源信息到每个文档块，以便后续处理。
    """
    formatted_strings = []
    for doc in docs:
        source = doc.metadata.get('source', '未知来源')
        if '/' in source or '\\' in source:
            filename = source.split('/')[-1].split('\\')[-1]
        else:
            filename = source
        
        formatted_string = f"来源文件名: {filename}\n内容: {doc.page_content}"
        formatted_strings.append(formatted_string)
        
    return "\n\n---\n\n".join(formatted_strings)


def _retrieve_and_format(question: str) -> str:
    """内部检索格式化函数，供 LCEL 链和评估模块调用。"""
    retriever = get_retriever_from_store()
    docs = retriever.invoke(question)
    if settings.RERANK_ENABLED:
        docs = rerank_documents_by_embedding(question, docs, settings.RERANK_TOP_N)
    elif len(docs) > settings.RERANK_TOP_N:
        docs = docs[: settings.RERANK_TOP_N]
    return _format_docs(docs)


# 公开别名：供 rag_evaluator 等外部模块直接调用，避免引用私有函数
retrieve_and_format_docs = _retrieve_and_format


def _normalize_input(x: str | Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧接口：仅传 question 字符串；新接口传 dict。"""
    if isinstance(x, str):
        return {"question": x, "history_block": ""}
    q = x.get("question", "")
    hb = x.get("history_block", "") or ""
    return {"question": q, "history_block": hb}


def get_qa_chain():
    """
    构建并返回 RAG 问答链（Prompt 来自 YAML，支持 history_block 注入多轮上下文）。

    Returns:
        Runnable: LCEL 链，输入为 str 或 {"question","history_block"}。
    """
    qa_prompt = build_qa_chat_template()

    rag_chain = (
        RunnableLambda(_normalize_input)
        | RunnablePassthrough.assign( 
            context=lambda x: _retrieve_and_format(x["question"]),
        )
        | qa_prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain
