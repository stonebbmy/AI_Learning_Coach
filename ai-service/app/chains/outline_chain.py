
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser

from ..core.llm import llm
from ..models.schemas import StudyOutlineResponse
from ..prompts.templates import outline_system_template, few_shot_examples

def get_outline_generation_chain():
    """
    构建并返回用于生成学习大纲的 LCEL (LangChain Expression Language) 链。

    该链的核心功能点：
    1.  **PydanticOutputParser**: 强制模型输出符合 `StudyOutlineResponse` Pydantic模型的JSON格式，
        确保了输出的结构化和可靠性。
    2.  **Few-shot Prompting**: 将一个高质量的示例直接注入到系统提示中，为模型提供清晰的模仿
        对象，从而显著提升生成大纲的质量和相关性。
    3.  **LCEL**: 使用 `|` 操作符将 Prompt, LLM, 和 Parser 优雅地串联起来，代码简洁且易于理解。

    Returns:
        Runnable: 一个可执行的 LangChain 链。
    """
    # 1. 初始化 Pydantic 输出解析器，它知道如何将LLM的输出解析为 StudyOutlineResponse 对象
    parser = PydanticOutputParser(pydantic_object=StudyOutlineResponse)

    # 2. 构建最终的 Prompt 模板
    # 我们将 few-shot 示例和原始系统指令结合，创建一个更丰富的上下文
    final_system_prompt = f"""
{outline_system_template.format(format_instructions=parser.get_format_instructions())}

这里是一个高质量的示例，请参考它的结构和内容深度：

--- 示例输入 ---
{few_shot_examples[0]['input']}

--- 示例输出 ---
{few_shot_examples[0]['output']}
--- 示例结束 ---
"""

    # 创建一个包含系统消息和人类消息的 Prompt 模板
    prompt = ChatPromptTemplate.from_messages([
        ("system", final_system_prompt),
        ("human", "请根据我的需求生成学习大纲。\n【学习目标】: {target}\n【期望期限】: {deadline}")
    ])

    # 3. 使用 LCEL 将 Prompt, LLM, 和 Parser 串联成链
    chain = prompt | llm | parser
    
    return chain

