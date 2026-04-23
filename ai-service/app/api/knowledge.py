import os
import shutil
from collections import defaultdict
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from datetime import datetime

from ..models.schemas import (
    StatusResponse,
    KnowledgeSummaryResponse,
    KnowledgeSourceItem,
    KnowledgeChunksResponse,
    KnowledgeChunkItem,
)
from ..rag.loader import load_markdown_file
from ..rag.splitter import get_text_splitter
from ..rag.vector_store import add_documents_to_store, get_vector_store

router = APIRouter()

_TEXT_PREVIEW_MAX = 4000

@router.get("/knowledge/summary", response_model=KnowledgeSummaryResponse)
def knowledge_summary():
    """
    查看知识库概览：总向量块数、按 source（文件名）聚合的条数与上传日期。
    数据来自 Chroma 集合 `ai_learning_notes` 的元数据。
    """
    try:
        col = get_vector_store()._collection
        n = col.count()
        if n == 0:
            return KnowledgeSummaryResponse(total_chunks=0, sources=[])
        raw = col.get(include=["metadatas"], limit=max(n, 1))
        metas = raw.get("metadatas") or []
        counts: dict[str, int] = defaultdict(int)
        dates: dict[str, str | None] = {}
        for m in metas:
            if not m:
                continue
            src = str(m.get("source") or "unknown")
            counts[src] += 1
            ud = m.get("upload_date")
            if isinstance(ud, str):
                prev = dates.get(src)
                if prev is None or ud > prev:
                    dates[src] = ud
        sources = [
            KnowledgeSourceItem(
                source=s,
                chunk_count=counts[s],
                upload_date=dates.get(s),
            )
            for s in sorted(counts.keys(), key=str.lower)
        ]
        return KnowledgeSummaryResponse(total_chunks=n, sources=sources)
    except Exception as e:
        print(f"[knowledge] summary error: {e}")
        raise HTTPException(status_code=500, detail=f"读取知识库失败: {e}") from e


@router.get("/knowledge/chunks", response_model=KnowledgeChunksResponse)
def knowledge_chunks(
    source: str | None = Query(None, description="仅查看某个 Markdown 源文件的块；不传则浏览全部（分页）"),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    分页查看已入库的文本块（截断展示），可筛选 source。
    """
    try:
        col = get_vector_store()._collection
        kwargs: dict = {
            "include": ["metadatas", "documents"],
            "limit": limit,
            "offset": offset,
        }
        if source and source.strip():
            kwargs["where"] = {"source": source.strip()}
        raw = col.get(**kwargs)
        ids = raw.get("ids") or []
        metas = raw.get("metadatas") or []
        docs = raw.get("documents") or []
        chunks: list[KnowledgeChunkItem] = []
        for i, did in enumerate(ids):
            m = metas[i] if i < len(metas) else None
            text = (docs[i] if i < len(docs) else None) or ""
            tlen = len(text)
            if tlen > _TEXT_PREVIEW_MAX:
                prev = text[:_TEXT_PREVIEW_MAX] + "…"
            else:
                prev = text
            mm = m or {}
            chunks.append(
                KnowledgeChunkItem(
                    id=did,
                    source=mm.get("source"),
                    upload_date=mm.get("upload_date") if isinstance(mm.get("upload_date"), str) else None,
                    text_preview=prev,
                    text_length=tlen,
                )
            )
        has_more = len(ids) == limit
        return KnowledgeChunksResponse(
            limit=limit, offset=offset, has_more=has_more, chunks=chunks
        )
    except Exception as e:
        print(f"[knowledge] chunks error: {e}")
        raise HTTPException(status_code=500, detail=f"读取分块失败: {e}") from e


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

    # 去重检查：若同名文件已存在于向量库，先删除旧数据再导入
    # 避免重复上传导致 Chroma 中出现冗余向量（影响检索质量）
    try:
        existing = get_vector_store().get(where={"source": file.filename})
        if existing and existing.get("ids"):
            get_vector_store().delete(ids=existing["ids"])
            print(f"Removed {len(existing['ids'])} old chunks for '{file.filename}'")
    except Exception as e:
        print(f"[knowledge] dedup check failed (non-fatal): {e}")
        
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

