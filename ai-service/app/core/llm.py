
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from .config import settings

# --------------------------------------------------------------------------
# LLM 和 Embedding 模型的单例初始化
# 这种方式可以确保在整个应用生命周期中，模型实例只被创建一次，
# 避免了不必要的资源消耗和重复加载。
# --------------------------------------------------------------------------

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

# 初始化 Embedding 模型
# 同样，使用 OpenAIEmbeddings 类，并将其指向 DeepSeek 的嵌入服务。
embeddings = OpenAIEmbeddings(
    model=settings.EMBEDDING_MODEL_NAME,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_API_BASE,
)

