---
name: run-ai-service
description: 启动、调试和验证 AI Learning Coach 的 ai-service 及依赖服务。用户提到启动服务、跑测试、docker-compose、本地开发环境时使用。
disable-model-invocation: true
---

# 运行 ai-service

## 方式一：Docker Compose（推荐）

在项目根目录：

```bash
docker compose up -d
curl http://localhost:8000/health
curl http://localhost:8000/api/health/detail
```

## 方式二：本地 Python

```bash
cd ai-service
pip install -r requirements.txt
# 确保根目录 .env 已配置 DEEPSEEK_API_KEY 等
uvicorn main:app --reload --port 8000
```

依赖服务（Redis、Chroma）需已通过 docker compose 启动。

## 常用验证命令

```bash
# RAG 冒烟
cd ai-service && python scripts/eval_smoke.py

# MCP 连通（web_search）
cd ai-service && python -c "
import asyncio
from app.tools.mcp_adapter import web_research
async def main():
    print(await web_research('FastAPI middleware', max_results=2))
asyncio.run(main())
"

# E2E 网络检查
cd ai-service && python scripts/e2e_network_check.py
```

## 排错速查

| 现象 | 检查 |
|------|------|
| 8000 连不上 | `docker compose ps`，看 ai-service 日志 |
| Embedding 失败 | `.env` 中 `EMBEDDING_API_KEY` / 硅基流动配置 |
| MCP 超时 | 网络/代理；DuckDuckGo 是否可达 |
| Redis 错误 | `docker compose up redis -d` |

## Agent 调试提示

- 带 `@Terminals` 把报错日志给 Agent
- 带 `@ai-service/app/tools/mcp_adapter.py` 定位 MCP 问题
- 复杂改动先用 Plan 模式出方案
