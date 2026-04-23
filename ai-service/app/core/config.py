
import os
from dotenv import load_dotenv

# 加载 .env 文件，以便在本地开发时使用
# 在 Docker 环境中，我们将通过 docker-compose.yml 直接注入环境变量
load_dotenv()

class Settings:
    """
    项目配置类，统一管理所有环境变量和敏感信息。

    设计原则：
    - 所有配置从环境变量读取，支持 12-Factor App 规范
    - 每个配置项都有安全的默认值，本地开发无需完整配置
    - 敏感信息（API Key 等）永远不硬编码，也不打印到日志
    - 类属性形式（非 Pydantic Settings）：简单直接，无额外依赖，
      若需要类型校验可迁移到 pydantic-settings（BaseSettings）
    """
    # --------------------------------------------------------------------------
    # 大模型（LLM）和嵌入（Embedding）模型配置
    # --------------------------------------------------------------------------
    # LLM：DeepSeek（OpenAI 兼容 Chat Completions）。
    # 嵌入：硅基流动等 OpenAI 兼容 /v1/embeddings（DeepSeek 无稳定嵌入接口）。
    
    # DeepSeek API Key
    # 请在项目根目录创建 .env 文件并添加 DEEPSEEK_API_KEY="your_actual_api_key"
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "your_deepseek_api_key")
    
    # DeepSeek API Base URL
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    
    # 对话模型的名称
    LLM_MODEL_NAME: str = "deepseek-chat"

    # --------------------------------------------------------------------------
    # 嵌入模型（与 LLM 分离）
    # Key 优先级：EMBEDDING_API_KEY > SILICONFLOW_API_KEY > OPENAI_API_KEY
    # 文档：https://docs.siliconflow.cn/cn/api-reference/embeddings/create-embeddings
    # --------------------------------------------------------------------------
    EMBEDDING_API_KEY: str = (
        os.getenv("EMBEDDING_API_KEY", "").strip()
        or os.getenv("SILICONFLOW_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    EMBEDDING_API_BASE: str = os.getenv(
        "EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1"
    ).rstrip("/")
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "BAAI/bge-m3"
    )
    EMBEDDING_TIKTOKEN_ENABLED: bool = os.getenv(
        "EMBEDDING_TIKTOKEN_ENABLED", "true"
    ).lower() in ("1", "true", "yes")

    # --------------------------------------------------------------------------
    # 向量数据库（ChromaDB）配置
    # --------------------------------------------------------------------------
    # Chroma 运行模式：
    # - remote: 连接 docker-compose 中的 chroma server（推荐，避免多 worker 本地 sqlite 依赖与一致性问题）
    # - embedded: 使用本地 PersistentClient（仅用于本地快速试验）
    CHROMA_MODE: str = os.getenv("CHROMA_MODE", "remote")

    # remote 模式配置（docker-compose 网络内：host=chroma, port=8000）
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "chroma")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8000"))

    # embedded 模式持久化路径
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    
    # 集合（Collection）名称，用于存储笔记向量
    CHROMA_COLLECTION_NAME: str = "ai_learning_notes"

    # --------------------------------------------------------------------------
    # RAG (Retrieval-Augmented Generation) 配置
    # --------------------------------------------------------------------------
    # 文本分割器的块大小
    CHUNK_SIZE: int = 500
    
    # 文本分割器的重叠大小
    CHUNK_OVERLAP: int = 50

    # --------------------------------------------------------------------------
    # Agent 配置
    # --------------------------------------------------------------------------
    # 是否开启 Agent 的详细思考过程日志
    AGENT_VERBOSE: bool = True

    # --------------------------------------------------------------------------
    # Prompt 版本（YAML：app/prompts/versions/qa_{version}.yaml）
    # --------------------------------------------------------------------------
    PROMPT_QA_VERSION: str = os.getenv("PROMPT_QA_VERSION", "v1")

    # --------------------------------------------------------------------------
    # RAG：检索后 Embedding 重排序（与 Java 里对 ES 结果做 rerank 类似）
    # --------------------------------------------------------------------------
    RERANK_ENABLED: bool = os.getenv("RERANK_ENABLED", "true").lower() in ("1", "true", "yes")
    RETRIEVAL_CANDIDATES: int = int(os.getenv("RETRIEVAL_CANDIDATES", "12"))
    RERANK_TOP_N: int = int(os.getenv("RERANK_TOP_N", "4"))

    # --------------------------------------------------------------------------
    # Redis（Python 侧：会话记忆、精确命中缓存）
    # --------------------------------------------------------------------------
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() in ("1", "true", "yes")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    CHAT_CACHE_TTL_SECONDS: int = int(os.getenv("CHAT_CACHE_TTL_SECONDS", "3600"))
    CHAT_SESSION_TTL_SECONDS: int = int(os.getenv("CHAT_SESSION_TTL_SECONDS", "86400"))
    CHAT_HISTORY_MAX_TURNS: int = int(os.getenv("CHAT_HISTORY_MAX_TURNS", "10"))
    CHAT_HISTORY_MAX_CHARS: int = int(os.getenv("CHAT_HISTORY_MAX_CHARS", "4000"))

    # --------------------------------------------------------------------------
    # 语义缓存（Chroma 独立 collection，复用同一 embedding）
    # --------------------------------------------------------------------------
    SEMANTIC_CACHE_ENABLED: bool = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    SEMANTIC_CACHE_COLLECTION: str = os.getenv("SEMANTIC_CACHE_COLLECTION", "semantic_qa_cache")
    SEMANTIC_CACHE_MAX_DISTANCE: float = float(os.getenv("SEMANTIC_CACHE_MAX_DISTANCE", "0.42"))

    SESSION_MEMORY_COLLECTION: str = os.getenv("SESSION_MEMORY_COLLECTION", "session_long_memory")
    LONG_MEMORY_ENABLED: bool = os.getenv("LONG_MEMORY_ENABLED", "false").lower() in ("1", "true", "yes")

    # --------------------------------------------------------------------------
    # Langfuse 可观测性（可选；未配置 key 时自动跳过）
    # --------------------------------------------------------------------------
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")

    # --------------------------------------------------------------------------
    # 多模态（可选：仅当配置了视觉模型时使用）
    # --------------------------------------------------------------------------
    VISION_MODEL_NAME: str = os.getenv("VISION_MODEL_NAME", "deepseek-chat")
    MULTIMODAL_ENABLED: bool = os.getenv("MULTIMODAL_ENABLED", "false").lower() in ("1", "true", "yes")

    # --------------------------------------------------------------------------
    # 限流配置（Redis 滑动窗口限流）
    # --------------------------------------------------------------------------
    # 是否启用限流（false = 不限流，适合本地开发）
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "false").lower() in ("1", "true", "yes")
    # 每个时间窗口内允许的最大请求数
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60"))
    # 时间窗口大小（秒）
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    # Redis Key 前缀（避免与其他项目冲突）
    RATE_LIMIT_KEY_PREFIX: str = os.getenv("RATE_LIMIT_KEY_PREFIX", "rl:aicoach")

    # --------------------------------------------------------------------------
    # API Key 鉴权配置
    # --------------------------------------------------------------------------
    # 是否启用 API Key 鉴权（false = 不鉴权，适合内网或本地开发）
    API_KEY_ENABLED: bool = os.getenv("API_KEY_ENABLED", "false").lower() in ("1", "true", "yes")
    # 合法的 API Key 列表（逗号分隔，支持多 Key 轮换）
    API_KEYS: str = os.getenv("API_KEYS", "dev-key-change-in-production")

    # --------------------------------------------------------------------------
    # 输入 Guardrails 配置
    # --------------------------------------------------------------------------
    # 用户输入的最大字符数（防止 Token 炸弹攻击）
    MAX_INPUT_LENGTH: int = int(os.getenv("MAX_INPUT_LENGTH", "4000"))

    # --------------------------------------------------------------------------
    # LLM 重试 & 超时配置（tenacity + asyncio）
    # --------------------------------------------------------------------------
    # LLM 调用失败时的最大重试次数（只重试 429/5xx/网络错误，不重试 400/401）
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    # 重试初始等待时间（秒）
    LLM_RETRY_WAIT_MIN: float = float(os.getenv("LLM_RETRY_WAIT_MIN", "1.0"))
    # 重试最大等待时间（秒，指数退避上限）
    LLM_RETRY_WAIT_MAX: float = float(os.getenv("LLM_RETRY_WAIT_MAX", "10.0"))
    # 每次 LLM 非流式调用的超时秒数（planner 节点等单次 ainvoke 场景）
    LLM_INVOKE_TIMEOUT: float = float(os.getenv("LLM_INVOKE_TIMEOUT", "60.0"))
    # LangGraph 计划生成图的总超时秒数（含多次 LLM + MCP 联网检索）
    PLAN_TIMEOUT_SECONDS: float = float(os.getenv("PLAN_TIMEOUT_SECONDS", "120.0"))
    # 流式 RAG 问答的总超时秒数（超时后发送 error 事件）
    CHAT_STREAM_TIMEOUT: float = float(os.getenv("CHAT_STREAM_TIMEOUT", "90.0"))

    # --------------------------------------------------------------------------
    # 熔断器（Circuit Breaker）配置
    # --------------------------------------------------------------------------
    # 触发熔断的连续失败次数阈值
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    # 熔断开启后的冷却时间（秒），冷却期内直接拒绝请求
    CIRCUIT_BREAKER_RESET_TIMEOUT: float = float(os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT", "30.0"))

    # --------------------------------------------------------------------------
    # 每 Session Token 配额（恶意消耗 Token 防护）
    # --------------------------------------------------------------------------
    # 单个 session 在 TTL 内允许消耗的最大 Token 数（0 = 不限制）
    SESSION_TOKEN_BUDGET: int = int(os.getenv("SESSION_TOKEN_BUDGET", "0"))
    # session Token 计数窗口（秒），窗口结束后自动清零（与会话 TTL 一致）
    SESSION_TOKEN_WINDOW: int = int(os.getenv("SESSION_TOKEN_WINDOW", "3600"))

# 创建一个全局可用的配置实例
settings = Settings()

