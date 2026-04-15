
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from typing import List
from langchain.schema.document import Document

def load_markdown_file(file_path: str) -> List[Document]:
    """
    加载并处理单个 Markdown 文件。

    Args:
        file_path (str): Markdown 文件的路径。

    Returns:
        List[Document]: 从 Markdown 文件加载的文档对象列表。
    """
    # UnstructuredMarkdownLoader 会将整个文件加载为一个 Document 对象
    loader = UnstructuredMarkdownLoader(file_path, mode="single")
    docs = loader.load()
    return docs

