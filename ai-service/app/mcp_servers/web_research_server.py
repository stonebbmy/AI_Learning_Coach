from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("ai-learning-coach-web-research")


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web and return a small list of results.

    Returns items: {title, url, snippet, source}
    """
    max_results = max(1, min(int(max_results), 10))

    # Minimal DuckDuckGo HTML scraping (no API key). Good enough for MVP.
    # If you later swap to an API-backed search, keep the tool contract stable.
    url = "https://duckduckgo.com/html/"
    params = {"q": query}

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
        trust_env=True,
    ) as client:
        resp = await client.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[Dict[str, Any]] = []
    for a in soup.select("a.result__a"):
        title = _normalize_ws(a.get_text(" "))
        href = a.get("href") or ""
        if not href:
            continue
        # Snippet nearby
        snippet_el = a.find_parent(class_="result__body")
        snippet = ""
        if snippet_el:
            snippet_text = snippet_el.select_one(".result__snippet")
            if snippet_text:
                snippet = _normalize_ws(snippet_text.get_text(" "))

        results.append(
            {
                "title": title,
                "url": href,
                "snippet": snippet,
                "source": "duckduckgo",
            }
        )
        if len(results) >= max_results:
            break

    return results


@mcp.tool()
async def web_fetch(url: str, max_chars: int = 6000) -> Dict[str, Any]:
    """
    Fetch a URL and return extracted plain text.

    Returns: {url, title, text}
    """
    max_chars = max(500, min(int(max_chars), 20000))
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are allowed.")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0),
        follow_redirects=True,
        trust_env=True,
    ) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = _normalize_ws(soup.title.string)  

    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = _normalize_ws(soup.get_text(" "))
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."

    return {"url": url, "title": title, "text": text}


if __name__ == "__main__":
    mcp.run()

