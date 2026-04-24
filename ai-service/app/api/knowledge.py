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


def _build_where(user_id: str | None, source: str | None) -> dict | None:
    """构造 Chroma where 过滤条件，支持 user_id 与 source 的组合过滤。"""
    conditions = []
    if user_id and user_id not in ("", "anonymous"):
        conditions.append({"owner": {"$eq": user_id}})
    if source and source.strip():
        conditions.append({"source": {"$eq": source.strip()}})
    if len(conditions) == 0:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


@router.get("/knowledge/summary", response_model=KnowledgeSummaryResponse)
def knowledge_summary(
    user_id: str | None = Query(None, description="按用户过滤；不传则查看全量知识库（管理员视角）"),
):
    """
    查看知识库概览：总向量块数、按 source（文件名）聚合的条数与上传日期。
    数据来自 Chroma 集合 `ai_learning_notes` 的元数据。
    """
    try:
        col = get_vector_store()._collection
        n = col.count()
        if n == 0:
            return KnowledgeSummaryResponse(total_chunks=0, sources=[])
        get_kwargs: dict = {"include": ["metadatas"], "limit": max(n, 1)}
        where = _build_where(user_id, None)
        if where:
            get_kwargs["where"] = where
        raw = col.get(**get_kwargs)
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
        return KnowledgeSummaryResponse(total_chunks=len(metas), sources=sources)
    except Exception as e:
        print(f"[knowledge] summary error: {e}")
        raise HTTPException(status_code=500, detail=f"读取知识库失败: {e}") from e


@router.get("/knowledge/chunks", response_model=KnowledgeChunksResponse)
def knowledge_chunks(
    source: str | None = Query(None, description="仅查看某个 Markdown 源文件的块；不传则浏览全部（分页）"),
    user_id: str | None = Query(None, description="按上传用户过滤"),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    分页查看已入库的文本块（截断展示），可筛选 source 和 user_id。
    """
    try:
        col = get_vector_store()._collection
        kwargs: dict = {
            "include": ["metadatas", "documents"],
            "limit": limit,
            "offset": offset,
        }
        where = _build_where(user_id, source)
        if where:
            kwargs["where"] = where
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
async def upload_knowledge(
    file: UploadFile = File(...),
    user_id: str = Query("anonymous", description="上传者用户 ID，写入 Chroma metadata 的 owner 字段"),
):
    """
    上传 Markdown 格式的学习笔记，将其处理并存入向量数据库。

    技术要点:
    1.  接收并暂存上传的 Markdown 文件。
    2.  使用 `RecursiveCharacterTextSplitter` 按配置切分文档。
    3.  为文档块添加文件名、上传日期、owner(user_id) 等元数据，支持多用户隔离检索。
    4.  调用向量库接口，将文档块向量化并持久化存储到 ChromaDB。
    """
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="仅支持 Markdown (.md) 文件。")

    # 去重检查：若同名文件 + 同一 owner 已存在，先删除旧数据再导入
    try:
        dedup_where: dict = {"source": {"$eq": file.filename}}
        if user_id and user_id != "anonymous":
            dedup_where = {"$and": [{"source": {"$eq": file.filename}}, {"owner": {"$eq": user_id}}]}
        existing = get_vector_store().get(where=dedup_where)
        if existing and existing.get("ids"):
            get_vector_store().delete(ids=existing["ids"])
            print(f"Removed {len(existing['ids'])} old chunks for '{file.filename}' (owner={user_id})")
    except Exception as e:
        print(f"[knowledge] dedup check failed (non-fatal): {e}")

    temp_dir = "data"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"Loading file: {file_path} (owner={user_id})")
        docs = load_markdown_file(file_path)

        upload_date = datetime.now().strftime("%Y-%m-%d")
        for doc in docs:
            doc.metadata["source"] = file.filename
            doc.metadata["upload_date"] = upload_date
            doc.metadata["owner"] = user_id

        text_splitter = get_text_splitter()
        split_docs = text_splitter.split_documents(docs)
        print(f"Split file into {len(split_docs)} chunks.")

        add_documents_to_store(split_docs)

        return StatusResponse(success=True, message=f"文件 '{file.filename}' 上传并处理成功。")
    except Exception as e:
        print(f"[Error] Failed to process upload: {e}")
        raise HTTPException(status_code=500, detail=f"处理文件时发生内部错误: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

