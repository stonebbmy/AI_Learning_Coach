
from fastapi import APIRouter, HTTPException
from ..models.schemas import OutlineGenerateRequest, StudyOutlineResponse
from ..chains.outline_chain import get_outline_generation_chain

router = APIRouter()

@router.post("/outline/generate", response_model=StudyOutlineResponse)
async def generate_outline(request: OutlineGenerateRequest):
    """
    根据用户目标和期限，生成结构化的学习大纲。
    
    技术要点:
    1.  **LCEL**: 调用预先构建好的 LCEL 链来执行任务。
    2.  **PydanticOutputParser**: 链中集成的解析器确保返回的数据符合 `StudyOutlineResponse` 模型。
    3.  **Few-shot Prompting**: 链中的 Prompt 包含了高质量示例，以引导模型输出。
    """
    try:
        print(f"Generating outline for target: '{request.target}'")
        # 获取预构建的链
        chain = get_outline_generation_chain()
        print("========= NEW CODE LOADED =========")
        
        # 异步调用链
        response = await chain.ainvoke({
            "target": request.target,
            "deadline": request.deadline
        })
        
        # 由于链的最后一步是 PydanticOutputParser，返回的已经是 Pydantic 对象
        return response
    except Exception as e:
        # 记录详细错误，便于调试
        print(f"[Error] Failed to generate study outline: {e}")
        # 返回给客户端一个通用的错误信息
        raise HTTPException(status_code=500, detail="生成学习大纲时发生内部错误。")

