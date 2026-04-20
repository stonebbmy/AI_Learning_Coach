
from typing import List

from langchain.schema.document import Document
from langchain_community.document_loaders import TextLoader


def load_markdown_file(file_path: str) -> List[Document]:
    """
    加载并处理单个 Markdown 文件。

    Args:
        file_path (str): Markdown 文件的路径。

    Returns:
        List[Document]: 从 Markdown 文件加载的文档对象列表。
    """
    # 接口仅接受 .md；纯文本加载即可，避免 unstructured 体积与依赖链
    loader = TextLoader(file_path, encoding="utf-8")
    docs = loader.load()
    return docs

