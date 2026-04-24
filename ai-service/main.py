"""
AI Learning Coach — AI Service 主入口

架构说明：
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                   │
├─────────────────────────────────────────────────────────┤
│  Middleware Stack（从外到内依次执行）                      │
│  1. CORSMiddleware     跨域请求处理                       │
│  2. ApiKeyAuthMiddleware  API Key 鉴权（可选）            │
│  3. SlidingWindowRateLimitMiddleware  限流（可选）         │
│  4. request_id_middleware  请求追踪 ID 注入               │
├─────────────────────────────────────────────────────────┤
│  Exception Handlers（统一异常格式化）                      │
│  AppException / RequestValidationError / Exception       │
├─────────────────────────────────────────────────────────┤
│  Routers                                                 │
│  /api/outline    学习大纲生成（LCEL + PydanticParser）    │
│  /api/knowledge  知识库（上传、概览、分块浏览）            │
│  /api/chat       RAG 问答（双层缓存 + SSE 流式）          │
│  /api/chat/agent ReAct Agent（LangGraph）                │
│  /api/plan       每日计划（LangGraph 状态机 + MCP）       │
│  /api/eval       RAG 质量评估（LLM-as-Judge）             │
│  /api/tutor      智能私教总控（意图分类+工具调度+SSE）     │
│  /metrics        可观测性指标（JSON + Prometheus）        │
│  /health         存活探针 / /health/detail 就绪探针       │
└─────────────────────────────────────────────────────────┘
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import outline, plan, chat, knowledge, chat_agent, multimodal, tutor
from app.api import metrics as metrics_router
from app.evaluation import rag_evaluator
from app.rag.vector_store import get_vector_store
from app.core.config import settings
from app.core.trace import new_request_id, set_request_id
from app.core.exceptions import register_exception_handlers
from app.middleware.rate_limit import SlidingWindowRateLimitMiddleware
from app.middleware.auth import ApiKeyAuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
    - Startup：预热 ChromaDB 连接（避免首次请求冷启动延迟）
    - Shutdown：打印关闭日志（可扩展：关闭连接池、刷写缓冲日志）
    """
    print("=" * 60)
    print("AI Learning Coach — AI Service 启动中...")
    print(f"  LLM 模型: {settings.LLM_MODEL_NAME}")
    print(f"  Embedding: {settings.EMBEDDING_MODEL_NAME}")
    print(f"  Chroma 模式: {settings.CHROMA_MODE}")
    print(f"  Redis 启用: {settings.REDIS_ENABLED}")
    print(f"  限流启用: {settings.RATE_LIMIT_ENABLED}")
    print(f"  API Key 鉴权: {settings.API_KEY_ENABLED}")
    print(f"  Guardrails 最大输入: {settings.MAX_INPUT_LENGTH} 字符")
    print(f"  Langfuse 追踪: {'启用' if settings.LANGFUSE_PUBLIC_KEY else '未配置'}")
    print("=" * 60)

    # 预热 ChromaDB：建立 HTTP 连接，避免第一次请求时冷启动（约 1-3s）
    print("预热 ChromaDB 连接...")
    get_vector_store()
    print("ChromaDB 就绪。")

    yield

    print("AI Service 正在关闭...")


# ---------------------------------------------------------------------------
# 创建 FastAPI 应用实例
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Learning Coach - AI Service",
    description=(
        "提供大模型调用、Agent决策、RAG检索等核心AI功能。\n\n"
        "**核心技术栈**：FastAPI + LangChain + LangGraph + ChromaDB + Redis\n\n"
        "**新增功能**：限流中间件 | API Key 鉴权 | Guardrails | RAG评估 | 可观测性指标"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# 注册全局异常处理器（必须在添加中间件之前注册）
# ---------------------------------------------------------------------------
register_exception_handlers(app)

# ---------------------------------------------------------------------------
# 中间件注册
#
# Starlette 规则：后注册的先执行（add_middleware 内部使用 insert(0, ...) 前插）
# 因此注册顺序与执行顺序「相反」——越晚 add_middleware 的，越靠外层、越先处理请求。
#
# 注册顺序（代码从上到下）→ 执行顺序（请求从外到内）：
#   4. request_id  ← 最先注册 = 最内层，在业务路由正前方注入 trace ID
#   3. 限流        ← 鉴权通过后再限流，防止未授权请求消耗限流配额
#   2. API Key 鉴权 ← CORS 之后，只鉴权业务请求
#   1. CORS        ← 最后注册 = 最外层，所有请求（含 preflight）先经过跨域检查
# ---------------------------------------------------------------------------

# 4. 请求追踪 ID（最内层：最先注册，执行时最靠近业务路由）
@app.middleware("http")
async def request_id_middleware(request, call_next):
    rid = request.headers.get("x-request-id") or new_request_id()
    set_request_id(rid)
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response

# 3. 限流（鉴权通过后再限流，防止未授权请求消耗限流配额）
app.add_middleware(SlidingWindowRateLimitMiddleware)

# 2. API Key 鉴权（CORS preflight 放行后，再鉴权业务请求）
app.add_middleware(ApiKeyAuthMiddleware)

# 1. CORS（最外层：最后注册，所有请求先经过跨域检查，含 OPTIONS preflight）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)

# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------
app.include_router(outline.router, prefix="/api", tags=["1. Learning Outline"])
app.include_router(knowledge.router, prefix="/api", tags=["2. Knowledge Base (RAG)"])
app.include_router(chat.router, prefix="/api", tags=["3. Chat (RAG + Cache)"])
app.include_router(chat_agent.router, prefix="/api", tags=["3b. Chat (ReAct Agent)"])
app.include_router(multimodal.router, prefix="/api", tags=["3c. Multimodal (Optional)"])
app.include_router(plan.router, prefix="/api", tags=["4. Daily Plan (LangGraph + MCP)"])
app.include_router(metrics_router.router, prefix="/api", tags=["5. Observability & Metrics"])
app.include_router(rag_evaluator.router, prefix="/api", tags=["6. RAG Evaluation"])
app.include_router(tutor.router, prefix="/api", tags=["7. Intelligent Tutor Orchestrator"])

# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------
@app.get("/health", tags=["_Health Check"])
def health_check():
    """
    快速存活探针（Liveness Probe）。
    仅返回 {"status": "ok"}，不检查依赖服务（快速响应）。
    就绪探针请使用 GET /api/health/detail。
    """
    return {"status": "ok"}

