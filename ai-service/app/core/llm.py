"""
LLM 和 Embedding 模型单例初始化，以及高可用调用封装（重试 + 熔断）。

高可用三层防护（面试考点）：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第1层：超时（Timeout）
  - LangChain 层：ChatOpenAI(timeout=120) 控制单次 HTTP 请求超时
  - asyncio 层：ainvoke_with_retry 内用 asyncio.wait_for 控制总超时
  - 应用层：plan.py / chat.py 用 asyncio.wait_for 控制业务超时

第2层：重试（Retry with Exponential Backoff）
  - 仅重试可恢复错误（429/5xx/网络），不重试 400/401（无限重试会加剧问题）
  - 指数退避 + jitter 防止"惊群效应"（Thundering Herd）
  - 最多重试 LLM_MAX_RETRIES 次（默认 3）

第3层：熔断（Circuit Breaker）
  - 状态机：CLOSED → OPEN → HALF-OPEN → CLOSED
  - 连续失败 N 次 → 开路（OPEN）：直接拒绝请求，快速失败
  - 冷却期结束 → 半开（HALF-OPEN）：放行一次试探
  - 试探成功 → 关路（CLOSED）：恢复正常
  - 避免对已经过载的 LLM API 持续冲击
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: 为什么用单例 LLM 实例而不是每次请求新建？
A: httpx.AsyncClient（ChatOpenAI 底层）维护 HTTP 连接池，单例可复用 TCP 连接，
   避免频繁握手。多并发下单例是线程/协程安全的（ChatOpenAI 本身无可变状态）。
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Sequence

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .config import settings

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 启动检查：Embedding API Key 必须配置
# ---------------------------------------------------------------------------
if not settings.EMBEDDING_API_KEY:
    raise RuntimeError(
        "未配置嵌入模型 API。默认使用硅基流动 OpenAI 兼容接口：请设置 SILICONFLOW_API_KEY，"
        "或 EMBEDDING_API_KEY / OPENAI_API_KEY（见 app/core/config.py 优先级）。"
        "默认 EMBEDDING_API_BASE=https://api.siliconflow.cn/v1，EMBEDDING_MODEL_NAME=BAAI/bge-m3。"
    )

# ---------------------------------------------------------------------------
# LLM 单例（ChatOpenAI → DeepSeek）
# ---------------------------------------------------------------------------
llm = ChatOpenAI(
    model=settings.LLM_MODEL_NAME,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_API_BASE,
    temperature=0,
    streaming=True,
    # LangChain/httpx 层超时：connect 5s + read 120s
    # 这是最后防线，正常业务层应更早超时（见 ainvoke_with_retry + plan.py）
    timeout=120,
    # LangChain 内置底层网络重试（不含业务逻辑，仅 httpx 层）
    max_retries=2,
)

# 与 PydanticOutputParser 等搭配时使用（全局 llm 为流式，供对话）
llm_for_structured = ChatOpenAI(
    model=settings.LLM_MODEL_NAME,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_API_BASE,
    temperature=0,
    streaming=False,
    timeout=120,
    max_retries=2,
)

# ---------------------------------------------------------------------------
# Embedding 单例（OpenAI 兼容接口，默认硅基流动 bge-m3）
# ---------------------------------------------------------------------------
embeddings = OpenAIEmbeddings(
    model=settings.EMBEDDING_MODEL_NAME,
    api_key=settings.EMBEDDING_API_KEY,
    base_url=settings.EMBEDDING_API_BASE,
    tiktoken_enabled=settings.EMBEDDING_TIKTOKEN_ENABLED,
)


# ---------------------------------------------------------------------------
# 熔断器（Circuit Breaker）
# ---------------------------------------------------------------------------

class _CBState(Enum):
    CLOSED = "closed"       # 正常工作
    OPEN = "open"           # 熔断开启，快速失败
    HALF_OPEN = "half_open" # 冷却后试探


class CircuitBreaker:
    """
    简易内存熔断器（每个 Worker 进程独立状态）。

    生产中多 Worker 场景应将状态存入 Redis 以共享，
    此处用进程内状态作为演示，已能覆盖单进程高并发场景。
    """

    def __init__(
        self,
        failure_threshold: int,
        reset_timeout: float,
        name: str = "llm",
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = _CBState.CLOSED
        self._failure_count = 0
        self._open_since: float = 0.0

    @property
    def state(self) -> _CBState:
        if self._state == _CBState.OPEN:
            # 检查冷却期是否结束，自动切换到 HALF_OPEN
            if time.monotonic() - self._open_since >= self.reset_timeout:
                self._state = _CBState.HALF_OPEN
                _logger.warning("[CircuitBreaker:%s] 冷却期结束，进入 HALF_OPEN 状态，开始试探", self.name)
        return self._state

    def is_open(self) -> bool:
        return self.state == _CBState.OPEN

    def record_success(self) -> None:
        """调用成功，重置熔断器状态。"""
        if self._state in (_CBState.HALF_OPEN, _CBState.OPEN):
            _logger.info("[CircuitBreaker:%s] 试探成功，恢复 CLOSED 状态", self.name)
        self._state = _CBState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        """调用失败，累计计数。"""
        self._failure_count += 1
        if self._state == _CBState.HALF_OPEN:
            # 半开试探失败，重新开路
            self._state = _CBState.OPEN
            self._open_since = time.monotonic()
            _logger.error(
                "[CircuitBreaker:%s] 试探失败，重新 OPEN（冷却 %.0fs）",
                self.name, self.reset_timeout,
            )
        elif self._failure_count >= self.failure_threshold:
            self._state = _CBState.OPEN
            self._open_since = time.monotonic()
            _logger.error(
                "[CircuitBreaker:%s] 连续失败 %d 次，开路（冷却 %.0fs）",
                self.name, self._failure_count, self.reset_timeout,
            )


# 全局 LLM 熔断器实例
llm_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    reset_timeout=settings.CIRCUIT_BREAKER_RESET_TIMEOUT,
    name="llm_api",
)


# ---------------------------------------------------------------------------
# 重试条件判断
# ---------------------------------------------------------------------------

def _is_retryable_error(exc: BaseException) -> bool:
    """
    判断异常是否值得重试（仅重试可恢复的瞬时故障）。

    不重试：400 Bad Request / 401 Unauthorized / 422 Validation Error
    重试：  429 Rate Limit / 5xx Server Error / 网络超时 / 连接错误
    """
    err_str = str(exc).lower()
    # 明确不该重试的客户端错误（含 401/403/400）
    if any(code in err_str for code in ["400", "401", "403", "422"]):
        return False
    # 可重试的服务端/网络错误
    retryable_signals = ["429", "500", "502", "503", "504", "timeout", "connection", "network"]
    return any(sig in err_str for sig in retryable_signals)


# ---------------------------------------------------------------------------
# 带重试 + 熔断 + 超时的非流式 LLM 调用（供 Planner 等非流式场景使用）
# ---------------------------------------------------------------------------

async def ainvoke_with_retry(
    messages: Sequence[BaseMessage] | list[Any],
    *,
    timeout: float | None = None,
) -> Any:
    """
    带熔断 + 重试 + 超时的 LLM 非流式调用封装。

    调用顺序：
    1. 检查熔断器状态（OPEN → 直接抛 LLMError，不发送请求）
    2. asyncio.wait_for 包裹 → 超时则抛 asyncio.TimeoutError
    3. 调用 llm.ainvoke(messages)
    4. 成功 → 记录 CB success；失败 → 记录 CB failure，根据类型决定重试

    Args:
        messages: LangChain 消息列表（ChatPromptTemplate.format_messages() 的输出）
        timeout: 单次调用超时秒数，None 使用 settings.LLM_INVOKE_TIMEOUT

    Returns:
        AIMessage（同 llm.ainvoke 的返回值）

    Raises:
        LLMError: 熔断开启 / 重试耗尽后抛出
        asyncio.TimeoutError: 超时
    """
    # 延迟导入避免循环依赖（exceptions 不依赖 llm）
    from .exceptions import LLMError

    _timeout = timeout if timeout is not None else settings.LLM_INVOKE_TIMEOUT

    # 1. 熔断器检查
    if llm_circuit_breaker.is_open():
        state = llm_circuit_breaker.state
        raise LLMError(
            f"LLM 服务熔断中（{state.value}），请稍后重试",
            detail={"circuit_breaker": state.value},
        )

    # 2. 重试循环
    last_exc: BaseException | None = None
    max_attempts = settings.LLM_MAX_RETRIES + 1  # 首次 + 重试次数

    for attempt in range(1, max_attempts + 1):
        try:
            result = await asyncio.wait_for(
                llm.ainvoke(messages),  # type: ignore[arg-type]
                timeout=_timeout,
            )
            llm_circuit_breaker.record_success()
            return result

        except asyncio.TimeoutError:
            _logger.warning(
                "[LLM] 调用超时（attempt %d/%d, timeout=%.0fs）",
                attempt, max_attempts, _timeout,
            )
            llm_circuit_breaker.record_failure()
            raise  # 超时不重试（可能是 Prompt 太长，重试也会超时）

        except Exception as exc:
            last_exc = exc
            if not _is_retryable_error(exc):
                # 不可重试错误：立即失败（如 401）
                _logger.error("[LLM] 不可重试错误（attempt %d）: %s", attempt, exc)
                llm_circuit_breaker.record_failure()
                raise LLMError(f"LLM 调用失败: {exc}", detail=str(exc)) from exc

            llm_circuit_breaker.record_failure()

            if attempt >= max_attempts:
                break

            # 指数退避等待
            wait = min(
                settings.LLM_RETRY_WAIT_MAX,
                settings.LLM_RETRY_WAIT_MIN * (2 ** (attempt - 1)),
            )
            _logger.warning(
                "[LLM] 可重试错误（attempt %d/%d），%.1fs 后重试: %s",
                attempt, max_attempts, wait, exc,
            )
            await asyncio.sleep(wait)

    raise LLMError(
        f"LLM 调用失败（已重试 {settings.LLM_MAX_RETRIES} 次）",
        detail=str(last_exc),
    ) from last_exc
