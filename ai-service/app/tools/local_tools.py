
import datetime
from langchain.tools import tool
from typing import List
from langchain.schema.document import Document

from ..rag.retriever import get_retriever_from_store

@tool
def get_current_time() -> str:
    """
    获取当前的日期和时间，格式为 YYYY-MM-DD HH:MM:SS。
    当用户询问今天或当前时间相关问题时，或在制定计划时，此工具非常有用。
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def search_my_notes(query: str) -> str:
    """
    在你的个人学习笔记中搜索与查询词（query）相关的信息。
    当你需要回顾、复习或基于已有知识进行规划时，使用此工具。
    例如，当用户说“复习一下昨天的LCEL知识”时，你可以用“LCEL”作为查询词。
    """
    print(f"Tool 'search_my_notes' called with query: {query}")
    try:
        retriever = get_retriever_from_store()
        
        # 使用检索器获取相关文档
        retrieved_docs: List[Document] = retriever.get_relevant_documents(query)
        
        if not retrieved_docs:
            return "在你的笔记中没有找到关于 '" + query + "' 的信息。"
            
        # 将检索到的文档内容格式化为字符串返回
        # 这为 Agent 提供了决策所需的上下文
        context = "\n\n---\n\n".join([f"来源: {doc.metadata.get('source', 'N/A')}\n内容:\n{doc.page_content}" for doc in retrieved_docs])
        
        return f"在你的笔记中找到了以下相关信息：\n\n{context}"
    except Exception as e:
        print(f"[Error] Failed to execute search_my_notes: {e}")
        return "搜索笔记时发生错误。"

