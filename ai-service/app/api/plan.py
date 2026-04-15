
import json
from fastapi import APIRouter, HTTPException
from ..models.schemas import DailyPlanRequest, DailyPlanResponse
from ..agents.planner import get_planner_agent_executor

router = APIRouter()

@router.post("/plan/daily", response_model=DailyPlanResponse)
async def generate_daily_plan(request: DailyPlanRequest):
    """
    使用 Agent 生成每日学习计划。
    
    技术要点:
    1.  **Agent + Tool Calling**: Agent 会根据目标决定是否调用 `search_my_notes` 等工具。
    2.  **真实检索**: `search_my_notes` 工具会真实调用 ChromaDB 进行 RAG 检索。
    3.  **Verbose Log**: `AgentExecutor` 的 `verbose=True` 会在控制台打印完整的思考过程。
    """
    try:
        print(f"Generating daily plan for goal: '{request.goal}'")
        agent_executor = get_planner_agent_executor()
        
        # 异步调用 Agent
        result = await agent_executor.ainvoke({
            "goal": request.goal
        })
        
        # Agent 的最终答案通常在 'output' 字段中
        output_str = result.get("output")
        if not output_str:
            raise HTTPException(status_code=500, detail="Agent 未能生成有效的计划。")

        print(f"Agent raw output:\n{output_str}")

        # Agent 的输出是一个 JSON 字符串，需要解析
        plan_data = json.loads(output_str)
        
        # 使用 Pydantic 模型进行验证和转换，然后返回
        return DailyPlanResponse(**plan_data)
        
    except json.JSONDecodeError:
        print(f"[Error] Agent returned a non-JSON output: {output_str}")
        raise HTTPException(status_code=500, detail="Agent 返回的计划格式无效。")
    except Exception as e:
        print(f"[Error] Failed to generate daily plan: {e}")
        raise HTTPException(status_code=500, detail="生成每日计划时发生内部错误。")

