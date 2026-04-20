
import os
from dotenv import load_dotenv

# 加载 .env 文件，以便在本地开发时使用
# 在 Docker 环境中，我们将通过 docker-compose.yml 直接注入环境变量
load_dotenv()

class Settings:
    """
    项目配置类，统一管理所有环境变量和敏感信息。
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
        "EMBEDDING_TIKTOKEN_ENABLED", "false"
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

# 创建一个全局可用的配置实例
settings = Settings()

