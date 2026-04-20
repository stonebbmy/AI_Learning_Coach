
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from ..models.schemas import ChatAgentRequest
from ..agents.react_agent import get_react_graph
from ..core.trace import get_request_id

router = APIRouter()


@router.post("/chat/agent")
async def chat_with_tools(request: ChatAgentRequest):
    """
    工具调用 Agent（非流式）：体现 ReAct / Tool-use 闭环。
    与 /chat 的纯 RAG 流式接口互补，便于面试讲解「何时用 Agent、何时用固定链」。
    """
    try:
        graph = get_react_graph()
        result = await graph.ainvoke({"messages": [HumanMessage(content=request.question)]})
        messages = result.get("messages") or []
        if not messages:
            raise ValueError("empty messages")
        last = messages[-1]
        out = getattr(last, "content", None) or str(last)
        return {
            "answer": out,
            "session_id": request.session_id,
            "request_id": get_request_id(),
        }
    except Exception as e:
        print(f"[chat/agent] {e}")
        raise HTTPException(status_code=500, detail="Agent 执行失败。") from e
