
import asyncio
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..models.schemas import ChatRequest
from ..agents.qa import get_qa_chain

router = APIRouter()

@router.post("/chat")
async def chat_with_rag(request: ChatRequest):
    """
    使用 RAG 和流式输出进行问答。
    
    技术要点:
    1.  **RAG 完整链路**: 调用预构建的 RAG 链进行问答。
    2.  **混合检索**: RAG 链内部使用 `EnsembleRetriever` 进行混合检索。
    3.  **SSE 流式输出**: 使用 `EventSourceResponse` 实现服务器发送事件 (SSE)，达成流式响应。
    4.  **答案来源标注**: 通过 Prompt Engineering 引导模型在答案中包含来源信息。
    """
    print(f"Received chat request: '{request.question}'")
    qa_chain = get_qa_chain()
    
    async def stream_generator():
        """一个异步生成器，用于从 RAG 链中流式获取数据并发送。"""
        try:
            # qa_chain.astream 会返回一个异步生成器，流式返回 LLM 的输出块
            async for chunk in qa_chain.astream(request.question):
                if chunk:
                    # 将每个块作为 SSE 事件发送出去
                    yield {"data": chunk}
                    # 短暂休眠，避免过于频繁地发送消息
                    await asyncio.sleep(0.01)
            # 发送一个结束信号（可选）
            yield {"event": "end", "data": ""}
        except Exception as e:
            print(f"[Error] Error during RAG stream: {e}")
            # 如果在流式处理中发生错误，发送一个错误事件
            yield {"event": "error", "data": "处理您的问题时发生错误。"}

    return EventSourceResponse(stream_generator())

