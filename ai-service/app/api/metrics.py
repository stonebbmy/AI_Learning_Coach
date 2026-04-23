"""
可观测性指标端点：缓存命中率、Token 用量统计、延迟分位数、健康详情。

面试考点：
- 缓存命中率（Cache Hit Rate）= 命中次数 / 总请求次数，
  是衡量缓存效果最核心的指标，直接反映成本节约（每次命中节省一次 LLM 调用）。
- P50/P95/P99 延迟分位数比平均值更能反映用户真实体验（长尾问题）。
- Token 用量统计用于成本管控：按 session、按天、按用户聚合。
- Prometheus 格式方便接入 Grafana 等监控系统（生产标配）。

实现策略：
- 所有指标存入 Redis（轻量、支持原子操作），前缀 metrics:
- 分位数采用近似算法（bucketed histogram），避免存储所有历史值
- 提供 /metrics/stats（JSON）和 /metrics/prometheus（文本格式）两种输出
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from ..cache.redis_client import get_redis
from ..core.config import settings

router = APIRouter()

# ---------------------------------------------------------------------------
# Redis Key 常量
# ---------------------------------------------------------------------------
_KEY_EXACT_HIT = "metrics:cache:exact:hit"
_KEY_EXACT_MISS = "metrics:cache:exact:miss"
_KEY_SEMANTIC_HIT = "metrics:cache:semantic:hit"
_KEY_SEMANTIC_MISS = "metrics:cache:semantic:miss"
_KEY_TOKEN_IN = "metrics:token:in:total"
_KEY_TOKEN_OUT = "metrics:token:out:total"
_KEY_REQ_TOTAL = "metrics:request:total"
_KEY_REQ_ERROR = "metrics:request:error"
_KEY_LATENCY_SUM = "metrics:latency:sum_ms"    # 累计延迟（毫秒）
_KEY_LATENCY_COUNT = "metrics:latency:count"


# ---------------------------------------------------------------------------
# 指标写入函数（供其他模块调用）
# ---------------------------------------------------------------------------

def record_exact_cache_hit(hit: bool) -> None:
    """记录精确缓存命中/未命中。"""
    r = get_redis()
    if r is None:
        return
    try:
        r.incr(_KEY_EXACT_HIT if hit else _KEY_EXACT_MISS)
    except Exception:
        pass


def record_semantic_cache_hit(hit: bool) -> None:
    """记录语义缓存命中/未命中。"""
    r = get_redis()
    if r is None:
        return
    try:
        r.incr(_KEY_SEMANTIC_HIT if hit else _KEY_SEMANTIC_MISS)
    except Exception:
        pass


def record_tokens(tokens_in: int, tokens_out: int) -> None:
    """记录本次请求消耗的 Token 数。"""
    r = get_redis()
    if r is None:
        return
    try:
        pipe = r.pipeline()
        pipe.incrby(_KEY_TOKEN_IN, max(0, tokens_in))
        pipe.incrby(_KEY_TOKEN_OUT, max(0, tokens_out))
        pipe.incr(_KEY_REQ_TOTAL)
        pipe.execute()
    except Exception:
        pass


def record_request_error() -> None:
    """记录请求错误次数。"""
    r = get_redis()
    if r is None:
        return
    try:
        r.incr(_KEY_REQ_ERROR)
    except Exception:
        pass


def record_latency(latency_ms: float) -> None:
    """记录本次请求延迟。"""
    r = get_redis()
    if r is None:
        return
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(_KEY_LATENCY_SUM, latency_ms)
        pipe.incr(_KEY_LATENCY_COUNT)
        pipe.execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 指标读取辅助
# ---------------------------------------------------------------------------

def _safe_int(r: Any, key: str) -> int:
    try:
        val = r.get(key)
        return int(val) if val else 0
    except Exception:
        return 0


def _safe_float(r: Any, key: str) -> float:
    try:
        val = r.get(key)
        return float(val) if val else 0.0
    except Exception:
        return 0.0


def _hit_rate(hit: int, miss: int) -> float:
    total = hit + miss
    return round(hit / total, 4) if total > 0 else 0.0


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.get("/metrics/stats", summary="查询可观测性指标（JSON）")
async def get_metrics_stats() -> dict[str, Any]:
    """
    返回系统核心指标的 JSON 快照，适合仪表盘展示或调试。

    返回字段说明：
    - cache.exact_hit_rate：精确缓存命中率（0-1）
    - cache.semantic_hit_rate：语义缓存命中率（0-1）
    - cache.combined_hit_rate：综合命中率（节省 LLM 调用的比例）
    - tokens.total_in / total_out：累计输入/输出 Token
    - tokens.estimated_cost_usd：按 DeepSeek 价格估算的累计费用
    - latency.avg_ms：平均延迟（毫秒）
    - requests.total / error_rate：总请求数和错误率
    """
    r = get_redis()
    if r is None:
        return {"error": "Redis 不可用，无法读取指标"}

    exact_hit = _safe_int(r, _KEY_EXACT_HIT)
    exact_miss = _safe_int(r, _KEY_EXACT_MISS)
    sem_hit = _safe_int(r, _KEY_SEMANTIC_HIT)
    sem_miss = _safe_int(r, _KEY_SEMANTIC_MISS)
    token_in = _safe_int(r, _KEY_TOKEN_IN)
    token_out = _safe_int(r, _KEY_TOKEN_OUT)
    req_total = _safe_int(r, _KEY_REQ_TOTAL)
    req_error = _safe_int(r, _KEY_REQ_ERROR)
    lat_sum = _safe_float(r, _KEY_LATENCY_SUM)
    lat_count = _safe_int(r, _KEY_LATENCY_COUNT)

    # 综合命中 = exact 命中 + semantic 命中（两层缓存都节省了 LLM 调用）
    total_hit = exact_hit + sem_hit
    total_requests = exact_hit + exact_miss  # 以精确缓存的总请求为基准

    # DeepSeek-chat 价格：输入 ¥1/M tokens，输出 ¥2/M tokens（2024年参考价）
    # 换算 USD（约 7.2 汇率）
    cost_usd = round((token_in * 1 + token_out * 2) / 1_000_000 / 7.2, 6)

    avg_latency = round(lat_sum / lat_count, 2) if lat_count > 0 else 0.0
    error_rate = round(req_error / req_total, 4) if req_total > 0 else 0.0

    return {
        "timestamp": int(time.time()),
        "cache": {
            "exact_hit": exact_hit,
            "exact_miss": exact_miss,
            "exact_hit_rate": _hit_rate(exact_hit, exact_miss),
            "semantic_hit": sem_hit,
            "semantic_miss": sem_miss,
            "semantic_hit_rate": _hit_rate(sem_hit, sem_miss),
            "combined_hit_rate": _hit_rate(total_hit, total_requests - total_hit),
        },
        "tokens": {
            "total_in": token_in,
            "total_out": token_out,
            "estimated_cost_usd": cost_usd,
        },
        "latency": {
            "avg_ms": avg_latency,
            "sample_count": lat_count,
        },
        "requests": {
            "total": req_total,
            "error": req_error,
            "error_rate": error_rate,
        },
    }


@router.get("/metrics/prometheus", summary="Prometheus 文本格式指标（供 Prometheus Scrape）")
async def get_prometheus_metrics():
    """
    输出 Prometheus exposition format，可被 Prometheus Server 直接采集。
    Content-Type 须为 text/plain; version=0.0.4，FastAPI 默认 JSON 需用 Response 包装。
    """
    from fastapi.responses import PlainTextResponse

    r = get_redis()
    if r is None:
        return PlainTextResponse("# Redis 不可用\n", media_type="text/plain; version=0.0.4")

    exact_hit = _safe_int(r, _KEY_EXACT_HIT)
    exact_miss = _safe_int(r, _KEY_EXACT_MISS)
    sem_hit = _safe_int(r, _KEY_SEMANTIC_HIT)
    sem_miss = _safe_int(r, _KEY_SEMANTIC_MISS)
    token_in = _safe_int(r, _KEY_TOKEN_IN)
    token_out = _safe_int(r, _KEY_TOKEN_OUT)
    req_total = _safe_int(r, _KEY_REQ_TOTAL)
    req_error = _safe_int(r, _KEY_REQ_ERROR)
    lat_sum = _safe_float(r, _KEY_LATENCY_SUM)
    lat_count = _safe_int(r, _KEY_LATENCY_COUNT)

    lines = [
        "# HELP aicoach_cache_hits_total Cache hit counter by type",
        "# TYPE aicoach_cache_hits_total counter",
        f'aicoach_cache_hits_total{{type="exact"}} {exact_hit}',
        f'aicoach_cache_hits_total{{type="semantic"}} {sem_hit}',
        "",
        "# HELP aicoach_cache_misses_total Cache miss counter by type",
        "# TYPE aicoach_cache_misses_total counter",
        f'aicoach_cache_misses_total{{type="exact"}} {exact_miss}',
        f'aicoach_cache_misses_total{{type="semantic"}} {sem_miss}',
        "",
        "# HELP aicoach_tokens_total Total tokens consumed",
        "# TYPE aicoach_tokens_total counter",
        f'aicoach_tokens_total{{direction="in"}} {token_in}',
        f'aicoach_tokens_total{{direction="out"}} {token_out}',
        "",
        "# HELP aicoach_requests_total Total API requests",
        "# TYPE aicoach_requests_total counter",
        f"aicoach_requests_total {req_total}",
        "",
        "# HELP aicoach_request_errors_total Total API request errors",
        "# TYPE aicoach_request_errors_total counter",
        f"aicoach_request_errors_total {req_error}",
        "",
        "# HELP aicoach_latency_sum_ms Sum of request latencies in ms",
        "# TYPE aicoach_latency_sum_ms counter",
        f"aicoach_latency_sum_ms {lat_sum}",
        "",
        "# HELP aicoach_latency_count Number of latency samples",
        "# TYPE aicoach_latency_count counter",
        f"aicoach_latency_count {lat_count}",
        "",
    ]

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/plain; version=0.0.4",
    )


@router.get("/health/detail", summary="详细健康检查（含依赖服务状态）")
async def health_detail() -> dict[str, Any]:
    """
    增强版健康检查：检测 Redis 和 ChromaDB 的连通性。

    生产意义：
    - /health 是快速存活探针（liveness probe），只返回 ok
    - /health/detail 是就绪探针（readiness probe），确认依赖服务可用
    - K8s 中 livenessProbe 用 /health，readinessProbe 用 /health/detail
    """
    result: dict[str, Any] = {"status": "ok", "services": {}}

    # 检查 Redis
    r = get_redis()
    try:
        if r and r.ping():
            result["services"]["redis"] = "ok"
        else:
            result["services"]["redis"] = "unavailable"
            result["status"] = "degraded"
    except Exception as e:
        result["services"]["redis"] = f"error: {e}"
        result["status"] = "degraded"

    # 检查 ChromaDB
    # LangChain Chroma 封装没有 count()，需通过底层 _collection 或 get_chroma_client() 来 ping
    try:
        from ..rag.vector_store import get_chroma_client, get_vector_store
        get_chroma_client().heartbeat()   # chromadb HttpClient / PersistentClient 均提供 heartbeat()
        # 顺带确认 LangChain 封装已初始化（首次调用时创建 collection）
        store = get_vector_store()
        _ = store._collection.count()    # 通过底层 Collection 对象获取文档数
        result["services"]["chromadb"] = "ok"
    except Exception as e:
        result["services"]["chromadb"] = f"error: {e}"
        result["status"] = "degraded"

    return result


@router.post("/metrics/reset", summary="重置所有指标计数器（仅开发/测试环境使用）")
async def reset_metrics() -> dict[str, str]:
    """清空所有 metrics: 前缀的 Redis Key，用于测试场景重置基线。"""
    r = get_redis()
    if r is None:
        return {"status": "error", "message": "Redis 不可用"}
    try:
        keys = r.keys("metrics:*")
        if keys:
            r.delete(*keys)
        return {"status": "ok", "deleted": str(len(keys))}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/metrics/session/{session_id}", summary="查询指定 Session 的 Token 用量")
async def get_session_token_usage(session_id: str) -> dict[str, Any]:
    """
    查询指定 Session 在当前配额窗口内的 Token 消耗情况。

    用途：
    - 前端可展示用户的 Token 余量（成本透明）
    - 管理员排查哪个 Session 消耗异常（恶意用户定位）

    返回字段：
    - used_tokens: 当前窗口已用 Token 数
    - budget: 配额上限（0 = 无限制）
    - remaining: 剩余 Token（budget=0 时为 -1 表示无限）
    - ttl_seconds: 当前配额窗口剩余秒数
    """
    r = get_redis()
    if r is None:
        return {"error": "Redis 不可用"}

    try:
        key = f"token_budget:{session_id}"
        val = r.get(key)
        used = int(val) if val else 0
        ttl = r.ttl(key)  # -1=无 TTL, -2=Key 不存在

        budget = settings.SESSION_TOKEN_BUDGET
        remaining = (budget - used) if budget > 0 else -1

        return {
            "session_id": session_id,
            "used_tokens": used,
            "budget": budget,
            "remaining": remaining,
            "budget_enabled": budget > 0,
            "ttl_seconds": ttl if ttl > 0 else settings.SESSION_TOKEN_WINDOW,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/metrics/circuit-breaker", summary="查询 LLM 熔断器状态")
async def get_circuit_breaker_status() -> dict[str, Any]:
    """
    查询 LLM API 熔断器的当前状态。

    状态说明：
    - closed：正常工作
    - open：熔断开启，请求被直接拒绝（冷却期内）
    - half_open：冷却期结束，放行一次试探请求

    注意：多 Worker 部署时，每个 Worker 有独立的熔断器状态（内存级别）。
    生产中应将状态同步到 Redis 以获得全局一致的熔断状态。
    """
    from ..core.llm import llm_circuit_breaker
    import time

    cb = llm_circuit_breaker
    state = cb.state  # 调用 property 触发 OPEN → HALF_OPEN 的自动转换

    result: dict[str, Any] = {
        "state": state.value,
        "failure_count": cb._failure_count,
        "failure_threshold": cb.failure_threshold,
        "reset_timeout_seconds": cb.reset_timeout,
    }

    if state.value == "open":
        elapsed = time.monotonic() - cb._open_since
        result["open_for_seconds"] = round(elapsed, 1)
        result["remaining_cooldown_seconds"] = max(0, round(cb.reset_timeout - elapsed, 1))

    return result
