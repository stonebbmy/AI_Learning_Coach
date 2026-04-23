
import asyncio
from fastapi import APIRouter

from ..models.schemas import OutlineGenerateRequest, StudyOutlineResponse
from ..chains.outline_chain import get_outline_generation_chain
from ..core.config import settings
from ..core.exceptions import LLMError
from ..guardrails.input_guard import enforce_input

router = APIRouter()


@router.post("/outline/generate", response_model=StudyOutlineResponse)
async def generate_outline(request: OutlineGenerateRequest):
    """
    根据用户目标和期限，生成结构化的学习大纲。

    技术栈展示：
    - LCEL：Prompt | LLM | PydanticOutputParser 三段式管道
    - PydanticOutputParser：强制 LLM 输出符合 StudyOutlineResponse 的 JSON 结构
    - Few-shot Prompting：系统 Prompt 中内嵌一个高质量示例，引导模型输出格式
    - Guardrails：对 target 字段做输入安全校验
    - asyncio.wait_for：总超时保护，防止 LLM 长时间挂起
    """
    # Guardrails：校验目标描述（最大长度，注入检测）
    enforce_input(request.target)

    print(f"Generating outline for target: '{request.target[:50]}'")
    chain = get_outline_generation_chain()

    try:
        response = await asyncio.wait_for(
            chain.ainvoke({"target": request.target, "deadline": request.deadline}),
            timeout=settings.LLM_INVOKE_TIMEOUT,
        )
        return response
    except asyncio.TimeoutError:
        raise LLMError(
            f"生成大纲超时（超过 {int(settings.LLM_INVOKE_TIMEOUT)}s），请简化学习目标后重试"
        )
    except Exception as e:
        print(f"[outline] error: {e}")
        raise LLMError(f"生成学习大纲时发生内部错误: {e}", detail=str(e)) from e
