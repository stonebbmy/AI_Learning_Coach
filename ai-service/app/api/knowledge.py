
import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime

from ..models.schemas import StatusResponse
from ..rag.loader import load_markdown_file
from ..rag.splitter import get_text_splitter
from ..rag.vector_store import add_documents_to_store

router = APIRouter()

@router.post("/knowledge/upload", response_model=StatusResponse)
async def upload_knowledge(file: UploadFile = File(...)):
    """
    上传 Markdown 格式的学习笔记，将其处理并存入向量数据库。
    
    技术要点:
    1.  接收并暂存上传的 Markdown 文件。
    2.  使用 `RecursiveCharacterTextSplitter` 按配置切分文档。
    3.  为文档块添加文件名和上传日期等元数据。
    4.  调用向量库接口，将文档块向量化并持久化存储到 ChromaDB。
    """
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="仅支持 Markdown (.md) 文件。")
        
    # 创建一个 موقت 目录来存放上传的文件
    temp_dir = "data"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file.filename)

    try:
        # 将上传的文件保存到磁盘
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 1. 加载文档
        print(f"Loading file: {file_path}")
        docs = load_markdown_file(file_path)
        
        # 2. 为文档添加元数据 (metadata)
        upload_date = datetime.now().strftime("%Y-%m-%d")
        for doc in docs:
            # 确保每个文档块都有文件名和日期作为元数据
            doc.metadata["source"] = file.filename
            doc.metadata["upload_date"] = upload_date
            
        # 3. 切分文档
        text_splitter = get_text_splitter()
        split_docs = text_splitter.split_documents(docs)
        print(f"Split file into {len(split_docs)} chunks.")
        
        # 4. 存入向量数据库
        add_documents_to_store(split_docs)
        
        return StatusResponse(success=True, message=f"文件 '{file.filename}' 上传并处理成功。")
    except Exception as e:
        print(f"[Error] Failed to process upload: {e}")
        raise HTTPException(status_code=500, detail=f"处理文件时发生内部错误: {str(e)}")
    finally:
        # 无论成功与否，都清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)

