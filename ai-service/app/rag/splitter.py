
from langchain.text_splitter import RecursiveCharacterTextSplitter
from ..core.config import settings

def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """
    获取一个根据项目配置初始化的文本分割器实例。
    
    遵循用户需求：chunk_size=500, overlap=50。
    我们使用 RecursiveCharacterTextSplitter，它会智能地按段落、句子等进行分割。

    Returns:
        RecursiveCharacterTextSplitter: 配置好的文本分割器实例。
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
        # 尝试按 Markdown 的结构进行分割
        separators=["\n\n", "\n", " ", "", "\u3002", "\uff0c"], # 中文句号和逗号
    )

