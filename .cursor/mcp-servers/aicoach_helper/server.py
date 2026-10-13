"""
Cursor IDE MCP Server — AI Learning Coach 项目助手（教学示例）

在 Cursor 聊天中可用工具：
- list_api_routes: 列出 ai-service 主要 API 路由
- get_architecture_summary: 返回架构文档摘要

启动方式见 .cursor/mcp.json
"""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("aicoach-helper")

# server.py 位于 .cursor/mcp-servers/aicoach_helper/
WORKSPACE = Path(__file__).resolve().parents[3]


@mcp.tool()
def list_api_routes() -> dict:
    """
    列出 ai-service 主要 HTTP API 路由（从 main.py 和 api/ 目录推断）。

    Returns: {routes: [{method, path, module}], note: str}
    """
    routes = [
        {"method": "POST", "path": "/api/knowledge/upload", "module": "knowledge"},
        {"method": "POST", "path": "/api/chat", "module": "chat (SSE RAG)"},
        {"method": "POST", "path": "/api/chat/agent", "module": "chat_agent (ReAct)"},
        {"method": "POST", "path": "/api/outline/generate", "module": "outline"},
        {"method": "POST", "path": "/api/plan/daily", "module": "plan (LangGraph)"},
        {"method": "POST", "path": "/api/eval/rag", "module": "evaluation"},
        {"method": "GET", "path": "/api/metrics/stats", "module": "metrics"},
        {"method": "GET", "path": "/api/health/detail", "module": "health"},
        {"method": "GET", "path": "/health", "module": "health (liveness)"},
    ]
    return {
        "routes": routes,
        "note": "完整架构见 docs/ARCHITECTURE.md；运行时以 main.py 注册为准",
    }


@mcp.tool()
def get_architecture_summary() -> dict:
    """
    返回 AI Learning Coach 架构一句话摘要与各层职责。

    Returns: {layers: [...], doc_path: str}
    """
    return {
        "doc_path": "docs/ARCHITECTURE.md",
        "layers": [
            {"name": "web", "stack": "Vue3", "port": 5173, "role": "前端 UI"},
            {"name": "java-app", "stack": "Spring Boot", "port": 8080, "role": "BFF / 用户上下文 / Feign"},
            {"name": "ai-service", "stack": "FastAPI + LangGraph", "port": 8000, "role": "RAG / Agent / MCP"},
            {"name": "ChromaDB", "stack": "向量库", "port": 8001, "role": "笔记 / 语义缓存 / 长期记忆"},
            {"name": "Redis", "stack": "缓存", "port": 6379, "role": "精确缓存 / 会话 / 限流"},
        ],
        "mcp_in_app": "ai-service/app/mcp_servers/web_research_server.py (web_search, web_fetch)",
        "mcp_in_cursor": ".cursor/mcp-servers/aicoach_helper/server.py (本 server)",
    }


@mcp.tool()
def find_file(hint: str) -> dict:
    """
    按关键词在 ai-service 下查找相关 Python 文件（简单 glob 匹配）。

    Args:
        hint: 关键词，如 mcp、rag、agent、plan

    Returns: {matches: [filepath, ...]}
    """
    hint = hint.strip().lower()
    if not hint:
        return {"matches": [], "error": "hint 不能为空"}

    ai_service = WORKSPACE / "ai-service"
    if not ai_service.is_dir():
        return {"matches": [], "error": f"未找到 ai-service 目录: {ai_service}"}

    matches: list[str] = []
    for path in ai_service.rglob("*.py"):
        rel = path.relative_to(WORKSPACE).as_posix()
        if hint in rel.lower() or hint in path.stem.lower():
            matches.append(rel)
        if len(matches) >= 15:
            break

    return {"matches": sorted(matches), "hint": hint}


if __name__ == "__main__":
    mcp.run()
