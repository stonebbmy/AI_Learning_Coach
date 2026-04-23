
import asyncio
from fastapi import APIRouter
from langchain_core.messages import HumanMessage

from ..models.schemas import ChatAgentRequest
from ..agents.react_agent import get_react_graph
from ..core.trace import get_request_id
from ..core.config import settings
from ..core.exceptions import LLMError, InputValidationError
from ..guardrails.input_guard import enforce_input

router = APIRouter()

# ReAct Agent 的总超时（含多轮工具调用），与 PLAN_TIMEOUT_SECONDS 复用同一配置
_AGENT_TIMEOUT = settings.PLAN_TIMEOUT_SECONDS


@router.post("/chat/agent")
async def chat_with_tools(request: ChatAgentRequest):
    """
    ReAct 工具调用 Agent（非流式）。

    工作流程：
    1. [安全] Guardrails 输入校验
    2. LangGraph prebuilt create_react_agent 驱动 ReAct 循环：
       思考(Thought) → 决定工具(Action) → 工具执行(Observation) → 再思考 → 最终回答
    3. asyncio.wait_for 控制整个 Agent 循环的总超时，防止工具调用无限循环
    4. 返回 JSON（非流式），可与 /api/chat 的 SSE 流式接口对比讲解选型

    可用工具：
    - get_current_time：获取当前日期时间
    - search_my_notes：在 Chroma 知识库中检索笔记（BM25 + 向量混合）
    """
    # 1. Guardrails
    enforce_input(request.question)

    print(f"[agent] session={request.session_id} question='{request.question[:50]}'")
    graph = get_react_graph()

    try:
        result = await asyncio.wait_for(
            graph.ainvoke({"messages": [HumanMessage(content=request.question)]}),
            timeout=_AGENT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise LLMError(
            f"Agent 执行超时（超过 {int(_AGENT_TIMEOUT)}s），请简化问题后重试",
            detail={"timeout_seconds": _AGENT_TIMEOUT},
        )
    except LLMError:
        raise
    except Exception as e:
        print(f"[agent] error: {e}")
        raise LLMError(f"Agent 执行失败: {e}", detail=str(e)) from e

    messages = result.get("messages") or []
    if not messages:
        raise LLMError("Agent 未返回任何消息")

    last = messages[-1]
    answer = getattr(last, "content", None) or str(last)

    return {
        "answer": answer,
        "session_id": request.session_id,
        "request_id": get_request_id(),
        "tool_calls_count": sum(
            1 for m in messages if getattr(m, "type", "") == "tool"
        ),
    }
