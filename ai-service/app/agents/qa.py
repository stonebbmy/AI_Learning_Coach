
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.schema.output_parser import StrOutputParser
from typing import List
from langchain.schema.document import Document

from ..rag.retriever import get_retriever_from_store
from ..prompts.templates import QA_PROMPT_TEMPLATE
from ..core.llm import llm

def _format_docs(docs: List[Document]) -> str:
    """
    一个辅助函数，将检索到的文档列表格式化为单个字符串，用作 RAG 的上下文。
    同时，它会提取并附加来源信息到每个文档块，以便后续处理。
    """
    # 重要的技术点：答案必须标注 `[来自: xxx.md]`
    # 我们在这里将 metadata 中的 source 附加到内容中，以便 LLM 能够看到并使用它。
    formatted_strings = []
    for doc in docs:
        source = doc.metadata.get('source', '未知来源')
        # 提取文件名
        if '/' in source or '\\' in source:
            filename = source.split('/')[-1].split('\\')[-1]
        else:
            filename = source
        
        formatted_string = f"来源文件名: {filename}\n内容: {doc.page_content}"
        formatted_strings.append(formatted_string)
        
    return "\n\n---\n\n".join(formatted_strings)


def get_qa_chain():
    """
    构建并返回 RAG (Retrieval-Augmented Generation) 问答链。

    这个链实现了完整的 RAG 链路，用于处理 `/chat` 接口的请求。
    技术要点：
    1.  **RAG 完整链路**: 实现了 Retriever -> Formatter -> Prompt -> LLM -> Parser 的经典流程。
    2.  **混合检索**: `get_retriever_from_store` 内部使用了 `EnsembleRetriever`，结合了向量和BM25检索。
    3.  **来源标注**: 通过 `_format_docs` 函数，将文档源信息注入上下文，引导LLM在答案中进行引用。

    Returns:
        Runnable: 一个可执行的 LangChain RAG 链。
    """
    retriever = get_retriever_from_store()
    
    # LCEL 链定义
    rag_chain = (
        # 1. 并行执行：一方面传递原始问题，另一方面通过检索器获取上下文
        {"context": retriever | RunnableLambda(_format_docs), "question": RunnablePassthrough()}
        # 2. 将问题和上下文填入 Prompt 模板
        | QA_PROMPT_TEMPLATE
        # 3. 将 Prompt 发送给 LLM
        | llm
        # 4. 将 LLM 的输出解析为字符串
        | StrOutputParser()
    )
    
    return rag_chain

