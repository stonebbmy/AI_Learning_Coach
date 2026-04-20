
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from .config import settings

# --------------------------------------------------------------------------
# LLM 和 Embedding 模型的单例初始化
# 这种方式可以确保在整个应用生命周期中，模型实例只被创建一次，
# 避免了不必要的资源消耗和重复加载。
# --------------------------------------------------------------------------

if not settings.EMBEDDING_API_KEY:
    raise RuntimeError(
        "未配置嵌入模型 API。默认使用硅基流动 OpenAI 兼容接口：请设置 SILICONFLOW_API_KEY，"
        "或 EMBEDDING_API_KEY / OPENAI_API_KEY（见 app/core/config.py 优先级）。"
        "默认 EMBEDDING_API_BASE=https://api.siliconflow.cn/v1，EMBEDDING_MODEL_NAME=BAAI/bge-m3。"
    )

# 初始化对话 LLM
# 我们使用 ChatOpenAI 类，但通过配置 api_key 和 base_url 将其指向 DeepSeek 服务。
# temperature=0 表示我们希望模型输出更具确定性，减少随机性，适合生成结构化数据或执行精确指令。
llm = ChatOpenAI(
    model=settings.LLM_MODEL_NAME,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_API_BASE,
    temperature=0,
    streaming=True # 默认开启流式，以便在 chat 接口中使用
)

# 初始化 Embedding 模型（独立 base_url / key，不经过 DeepSeek）
embeddings = OpenAIEmbeddings(
    model=settings.EMBEDDING_MODEL_NAME,
    api_key=settings.EMBEDDING_API_KEY,
    base_url=settings.EMBEDDING_API_BASE,
    tiktoken_enabled=settings.EMBEDDING_TIKTOKEN_ENABLED,
)
