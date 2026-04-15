
import tiktoken

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    计算给定文本的 token 数量。
    
    这对于在将文本发送给 LLM 之前估算成本或确保不超过上下文长度限制非常有用。
    我们使用 `tiktoken` 库，这是 OpenAI 官方使用的分词器。
    
    Args:
        text (str): 需要计算 token 的文本。
        model (str): 模型名称，分词方式与模型相关。默认为 "gpt-4"，对于DeepSeek等模型也适用。
        
    Returns:
        int: 文本对应的 token 数量。
    """
    try:
        # 获取与指定模型对应的编码器
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # 如果模型名称无效（例如，一些开源模型没有直接映射），
        # 使用一个通用的、广泛兼容的编码器 cl100k_base。
        encoding = tiktoken.get_encoding("cl100k_base")
        
    # 对文本进行编码，并返回编码后列表的长度
    return len(encoding.encode(text))

