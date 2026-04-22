
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from langchain.tools import Tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..core.trace import get_request_id

def _default_allowlist_domains() -> List[str]:
    """web_fetch 允许的域名；可用环境变量 MCP_WEB_ALLOW_DOMAINS 覆盖（逗号分隔）。"""
    return [
        "python.langchain.com",
        "docs.trychroma.com",
        "modelcontextprotocol.io",
        "github.com",
        "python.org",
        "docs.python.org",
        "readthedocs.io",
        "developer.mozilla.org",
        "stackoverflow.com",
        "stackexchange.com",
        "wikipedia.org",
        "medium.com",
        "dev.to",
        "arxiv.org",
        "huggingface.co",
        "pytorch.org",
        "tensorflow.org",
        "numpy.org",
        "pandas.pydata.org",
        "matplotlib.org",
        "kubernetes.io",
        "docker.com",
        "docs.docker.com",
        "learn.microsoft.com",
        "microsoft.com",
        "oracle.com",
        "kotlinlang.org",
        "go.dev",
        "golang.org",
        "rust-lang.org",
        "nginx.org",
        "w3.org",
        "ietf.org",
        "rfc-editor.org",
        "duckduckgo.com",
        "google.com",
        "googleapis.com",
        "pypi.org",
        "anaconda.com",
        "conda.io",
        "jupyter.org",
        "openai.com",
        "anthropic.com",
        "langchain.com",
        "trychroma.com",
        "siliconflow.cn",
        "realpython.com",
        "w3schools.com",
    ]


def _allowlist_domains() -> List[str]:
    raw = os.getenv("MCP_WEB_ALLOW_DOMAINS", "").strip()
    if not raw:
        return _default_allowlist_domains()
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _url_hostname(url: str) -> str:
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    return (urlparse(u).hostname or "").lower()


def _is_allowed_url(url: str) -> bool:
    allow = _allowlist_domains()
    if not allow:
        return False
    host = _url_hostname(url)
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


def _normalize_search_results(raw: Any) -> List[Dict[str, Any]]:
    """MCP / FastMCP 有时把列表序列化成 JSON 数组，json.loads 后为 list；个别路径会变成单条 dict。"""
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


async def web_research(query: str, *, max_results: int = 3, max_chars: int = 4000) -> str:
    """
    High-level helper used by LangGraph nodes.
    Returns a compact context string with citations.
    """
    max_results = max(1, min(int(max_results), 5))
    raw = await _call_mcp_tool("web_search", {"query": query, "max_results": max_results})
    search_results = _normalize_search_results(raw)
    if not search_results:
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

