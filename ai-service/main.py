
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import outline, plan, chat, knowledge
from app.rag.vector_store import get_vector_store
from app.core.config import settings
from app.core.trace import new_request_id, set_request_id

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理函数。
    在应用启动时执行预热操作，在关闭时执行清理操作。
    """
    # --- Startup --- 
    print("Application startup: Initializing vector store...")
    # 预热 ChromaDB，确保首次请求时连接已建立。
    get_vector_store()
    print("Vector store initialized.")
    print(f"Agent verbose mode: {'On' if settings.AGENT_VERBOSE else 'Off'}")
    yield
    # --- Shutdown ---
    print("Application shutdown.")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="AI Learning Coach - AI Service",
    description="提供大模型调用、Agent决策、RAG检索等核心AI功能。",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple request-id middleware for traceable logs (no external deps).
@app.middleware("http")
async def request_id_middleware(request, call_next):
    rid = request.headers.get("x-request-id") or new_request_id()
    set_request_id(rid)
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response

# 包含各个模块的 API 路由
app.include_router(outline.router, prefix="/api", tags=["1. Learning Outline"])
app.include_router(knowledge.router, prefix="/api", tags=["2. Knowledge Base (RAG)"])
app.include_router(chat.router, prefix="/api", tags=["3. Chat (RAG)"])
app.include_router(plan.router, prefix="/api", tags=["4. Daily Plan (Agent)"])

@app.get("/health", tags=["_Health Check"])
def health_check():
    """
    健康检查端点，供 Docker Compose 或其他监控工具使用。
    返回 `{"status": "ok"}` 表示服务正常。
    """
    return {"status": "ok"}

# 为了方便调试，可以在这里直接运行 uvicorn
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

