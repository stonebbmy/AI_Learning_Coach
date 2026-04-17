
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from langchain.tools import Tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..core.trace import get_request_id

def _allowlist_domains() -> List[str]:
    raw = os.getenv("MCP_WEB_ALLOW_DOMAINS", "").strip()
    if not raw:
        # 默认允许常见技术文档域名；可按需扩展
        return [
            "python.langchain.com",
            "docs.trychroma.com",
            "modelcontextprotocol.io",
            "github.com",
        ]
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _is_allowed_url(url: str) -> bool:
    allow = _allowlist_domains()
    if not allow:
        return False
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allow)


async def _call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Connect to the bundled MCP web-research server over stdio, call a tool, return JSON-like result.

    For MVP simplicity, we create a new session per call. (Easy to reason about; can be pooled later.)
    """
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "app.mcp_servers.web_research_server"],
    )

    rid = get_request_id()
    print(f"[rid={rid}] MCP call_tool start: {tool_name} args={list(arguments.keys())}")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

    print(f"[rid={rid}] MCP call_tool done: {tool_name}")

    # The python-sdk returns a structured result with content blocks.
    # We normalize to plain python objects (text blocks are expected).
    if hasattr(result, "content"):
        for c in result.content:
            if getattr(c, "type", None) == "text":
                try:
                    return json.loads(c.text)
                except Exception:
                    return c.text
    return result


async def web_research(query: str, *, max_results: int = 3, max_chars: int = 4000) -> str:
    """
    High-level helper used by LangGraph nodes.
    Returns a compact context string with citations.
    """
    max_results = max(1, min(int(max_results), 5))
    search_results = await _call_mcp_tool("web_search", {"query": query, "max_results": max_results})
    if not isinstance(search_results, list) or not search_results:
        return ""

    lines: List[str] = []
    for i, item in enumerate(search_results, start=1):
        url = str(item.get("url", ""))
        title = str(item.get("title", ""))
        snippet = str(item.get("snippet", ""))
        lines.append(f"[{i}] {title}\nURL: {url}\nSnippet: {snippet}".strip())

    # Fetch top-1 allowed page as supporting context (bounded)
    top_url = str(search_results[0].get("url", ""))
    if top_url and _is_allowed_url(top_url):
        fetched = await _call_mcp_tool("web_fetch", {"url": top_url, "max_chars": max_chars})
        if isinstance(fetched, dict):
            lines.append(
                "\n".join(
                    [
                        "---",
                        f"FetchedTitle: {fetched.get('title','')}",
                        f"FetchedURL: {fetched.get('url','')}",
                        f"FetchedText: {fetched.get('text','')}",
                    ]
                ).strip()
            )

    return "\n\n".join(lines).strip()


def get_mcp_tools() -> List[Tool]:
    """
    Export MCP tools as LangChain tools (for compatibility / future agent usage).

    NOTE: LangGraph nodes in this repo may call `web_research()` directly for now.
    """

    async def _search(query: str) -> str:
        data = await _call_mcp_tool("web_search", {"query": query, "max_results": 5})
        return json.dumps(data, ensure_ascii=False)

    async def _fetch(url: str) -> str:
        if not _is_allowed_url(url):
            return json.dumps({"error": "URL domain not allowed"}, ensure_ascii=False)
        data = await _call_mcp_tool("web_fetch", {"url": url, "max_chars": 6000})
        return json.dumps(data, ensure_ascii=False)

    return [
        Tool(
            name="mcp_web_search",
            coroutine=_search,
            func=lambda q: json.dumps({"error": "async only"}, ensure_ascii=False),
            description="MCP tool: web search. Input: query string. Output: JSON list of results.",
        ),
        Tool(
            name="mcp_web_fetch",
            coroutine=_fetch,
            func=lambda u: json.dumps({"error": "async only"}, ensure_ascii=False),
            description="MCP tool: fetch a URL (allowlisted domains only). Input: url string. Output: JSON dict.",
        ),
    ]

