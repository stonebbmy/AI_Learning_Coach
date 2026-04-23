"""
每日学习计划生成 API。

高可用改造：
- asyncio.wait_for 控制 LangGraph 整图总超时（PLAN_TIMEOUT_SECONDS）
  场景：多次 LLM 调用 + MCP 联网检索可能耗时 30-90s，必须有总超时兜底
- LLMError / AppException 替代裸 HTTPException，统一异常格式
- 超时后向前端返回 504 而非连接挂起

调用链路：
  POST /api/plan/daily
    → asyncio.wait_for(graph.ainvoke(), timeout=120s)
    → analyze_goal → retrieve_notes → web_research(MCP)
    → draft_plan[ainvoke_with_retry] → validate_plan
    → (repair_plan[ainvoke_with_retry] → validate_plan) × ≤2
    → 返回 DailyPlanResponse JSON
"""

import asyncio
from fastapi import APIRouter

from ..models.schemas import DailyPlanRequest, DailyPlanResponse
from ..graphs.planner_graph import get_planner_graph
from ..core.config import settings
from ..core.exceptions import LLMError, AppException
from ..core.trace import get_request_id

router = APIRouter()


@router.post("/plan/daily", response_model=DailyPlanResponse)
async def generate_daily_plan(request: DailyPlanRequest):
    """
    使用 LangGraph 工作流生成每日学习计划。

    技术栈展示：
    - LangGraph：有向状态机，节点间共享 PlannerState
    - MCP：web_search 联网检索补充上下文
    - ainvoke_with_retry：重试 + 熔断 + 超时三重保护
    - asyncio.wait_for：整图总超时，防止长任务悬挂
    - JSON 修复循环（repair 节点）：最多修复 2 次，有次数上限防无限循环
    """
    print(f"[rid={get_request_id()}] plan.generate_daily_plan: goal='{request.goal[:50]}'")
    graph = get_planner_graph()

    try:
        # 整图总超时：含 LLM 调用 + MCP 联网检索 + 最多 2 次修复
        final_state = await asyncio.wait_for(
            graph.ainvoke({"goal": request.goal}),
            timeout=settings.PLAN_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        print(f"[rid={get_request_id()}] plan timeout after {settings.PLAN_TIMEOUT_SECONDS}s")
        raise AppException(
            message=f"计划生成超时（超过 {int(settings.PLAN_TIMEOUT_SECONDS)}s），请简化目标描述后重试",
            detail={"timeout_seconds": settings.PLAN_TIMEOUT_SECONDS},
        )
    except LLMError:
        raise  # 已是规范异常，直接上抛给全局处理器
    except Exception as e:
        print(f"[rid={get_request_id()}] plan failed: {e}")
        raise LLMError(f"生成每日计划时发生错误: {e}", detail=str(e)) from e

    plan_data = final_state.get("plan")
    if not plan_data:
        raw = final_state.get("plan_raw", "")
        err = final_state.get("validation_error", "")
        print(f"[rid={get_request_id()}] plan invalid. raw={raw[:100]} err={err}")
        raise LLMError(
            "Planner 未能生成有效的计划（JSON 格式错误，已重试 2 次）",
            detail={"validation_error": err, "plan_raw_preview": raw[:200]},
        )

    return DailyPlanResponse(**plan_data)
