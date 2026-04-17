
import json
from fastapi import APIRouter, HTTPException
from ..models.schemas import DailyPlanRequest, DailyPlanResponse
from ..graphs.planner_graph import get_planner_graph

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
        graph = get_planner_graph()

        # 运行 LangGraph 工作流
        final_state = await graph.ainvoke({"goal": request.goal})
        plan_data = final_state.get("plan")

        if not plan_data:
            raw = final_state.get("plan_raw")
            err = final_state.get("validation_error")
            print(f"[Error] Planner graph failed. raw={raw}\nerror={err}")
            raise HTTPException(status_code=500, detail="Planner 未能生成有效的计划。")

        return DailyPlanResponse(**plan_data)
        
    except Exception as e:
        print(f"[Error] Failed to generate daily plan: {e}")
        raise HTTPException(status_code=500, detail="生成每日计划时发生内部错误。")

