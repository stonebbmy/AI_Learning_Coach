
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
    # 项目要求使用 DeepSeek 作为 LLM 和 Embedding 模型。
    # 我们将使用 langchain-openai 库，通过指定 API Base 来访问 DeepSeek 的兼容 OpenAI 的接口。
    
    # DeepSeek API Key
    # 请在项目根目录创建 .env 文件并添加 DEEPSEEK_API_KEY="your_actual_api_key"
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "your_deepseek_api_key")
    
    # DeepSeek API Base URL
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    
    # 对话模型的名称
    LLM_MODEL_NAME: str = "deepseek-chat"
    
    # 嵌入模型的名称
    # 注意：虽然原始需求提到了 DashScopeEmbeddings，但为保持一致性并遵循“deepseek作为...Embedding模型”的要求，
    # 我们在这里使用 DeepSeek 的嵌入模型。
    EMBEDDING_MODEL_NAME: str = "deepseek-text-embedding"

    # --------------------------------------------------------------------------
    # 向量数据库（ChromaDB）配置
    # --------------------------------------------------------------------------
    # ChromaDB 持久化路径
    CHROMA_DB_PATH: str = "./chroma_db"
    
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

