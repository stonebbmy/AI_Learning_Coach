from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import httpx


AI_SERVICE_BASE = "http://localhost:8000"


@dataclass
class CaseResult:
    name: str
    ok: bool
    latency_ms: int
    detail: str = ""


def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def run() -> List[CaseResult]:
    results: List[CaseResult] = []
    client = httpx.Client(timeout=30.0)

    # 1) health
    t0 = time.time()
    r = client.get(f"{AI_SERVICE_BASE}/health")
    ok = r.status_code == 200 and r.json().get("status") == "ok"
    results.append(CaseResult("health", ok, _ms(t0), detail=str(r.text)[:200]))

    # 2) plan/daily schema-ish check
    t0 = time.time()
    r = client.post(
        f"{AI_SERVICE_BASE}/api/plan/daily",
        json={"goal": "生成一份今天学习 LangGraph 的计划（包含可执行任务与预计时间）"},
        headers={"x-request-id": "eval-smoke"},
    )
    try:
        data = r.json()
        ok = (
            r.status_code == 200
            and isinstance(data.get("plan_title"), str)
            and isinstance(data.get("tasks"), list)
            and 3 <= len(data["tasks"]) <= 5
        )
        results.append(CaseResult("plan_daily", ok, _ms(t0), detail=json.dumps(data, ensure_ascii=False)[:200]))
    except Exception as e:
        results.append(CaseResult("plan_daily", False, _ms(t0), detail=f"status={r.status_code} err={e} body={r.text[:200]}"))

    client.close()
    return results


if __name__ == "__main__":
    out = run()
    for r in out:
        print(f"{r.name}\tok={r.ok}\tlatency_ms={r.latency_ms}\t{r.detail}")
    failed = [x for x in out if not x.ok]
    raise SystemExit(1 if failed else 0)

