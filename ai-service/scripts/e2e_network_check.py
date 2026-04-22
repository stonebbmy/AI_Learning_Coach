"""
在 ai-service 容器内运行，模拟 compose 环境下的外网链路。
用法: docker exec aicoach_ai_service sh -c "cd /app && PYTHONPATH=/app python /app/scripts/e2e_network_check.py"
"""
from __future__ import annotations

import asyncio
import os
import socket
import sys


def _print_resolv() -> None:
    print("--- 0) /etc/resolv.conf ---")
    try:
        with open("/etc/resolv.conf") as f:
            print(f.read().strip()[:500])
    except Exception as e:
        print(f"  (skip) {e}")


def _print_env() -> None:
    print("--- 1) 代理环境变量 ---")
    for k in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "NO_PROXY",
        "no_proxy",
    ):
        v = os.environ.get(k)
        print(f"  {k}={v!r}")


def _dns_hint(host: str) -> None:
    print(f"--- 2) DNS 解析 {host}:80 / :443（前几条）---")
    try:
        for fam, *_ in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)[:6]:
            fam_name = "IPv4" if fam == socket.AF_INET else "IPv6" if fam == socket.AF_INET6 else str(fam)
            print(f"  {fam_name}")
    except Exception as e:
        print(f"  FAIL: {e}")


def _httpx_compare() -> None:
    import httpx

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    print("--- 3) 解析 host.docker.internal / 外网域名（用于对照 httpx）---")
    for h in ("host.docker.internal", "www.google.com", "duckduckgo.com"):
        try:
            print(f"  gethostbyname({h}) = {socket.gethostbyname(h)}")
        except Exception as e:
            print(f"  gethostbyname({h}) FAIL: {e}")
    print("--- 4) httpx 对比：trust_env vs 显式 proxy（同一 Clash）---")
    for name, url in (
        ("google", "https://www.google.com"),
        ("duckduckgo-html", "https://duckduckgo.com/html/?q=test"),
    ):
        try:
            r = httpx.get(
                url,
                timeout=25.0,
                follow_redirects=True,
                trust_env=True,
            )
            print(f"  {name} trust_env: status={r.status_code} len={len(r.text)}")
        except Exception as e:
            print(f"  {name} trust_env: FAIL {type(e).__name__}: {e}"[:200])
        if proxy:
            try:
                r = httpx.get(
                    url,
                    timeout=25.0,
                    follow_redirects=True,
                    trust_env=False,
                    proxy=proxy,
                )
                print(f"  {name} explicit proxy: status={r.status_code} len={len(r.text)}")
            except Exception as e:
                print(f"  {name} explicit proxy: FAIL {type(e).__name__}: {e}"[:200])


async def _mcp_web_search() -> None:
    print("--- 5) MCP web_research（白名单 + DuckDuckGo）---")
    try:
        from app.tools.mcp_adapter import web_research

        text = await web_research("python asyncio tutorial", max_results=2, max_chars=800)
        if text:
            preview = text[:1200] + ("..." if len(text) > 1200 else "")
            print(f"  OK len={len(text)}\n{preview}")
        else:
            print("  EMPTY (无结果或解析失败)")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        raise


def main() -> int:
    os.chdir("/app")
    sys.path.insert(0, "/app")

    _print_resolv()
    _print_env()
    _dns_hint("www.google.com")
    _dns_hint("duckduckgo.com")
    _httpx_compare()
    asyncio.run(_mcp_web_search())
    print("--- 完成 ---")
    print(
        "说明：若曾出现 gethostbyname(host.docker.internal) 失败，compose 已用 extra_hosts:host-gateway 修复；"
        "修复前 HTTP_PROXY 无法解析，httpx 会报 Name or service not known，且直连外网域名可能拿到错误解析。\n"
        "Google 与 DuckDuckGo：站点与 Clash 分流不同；本业务搜索走 DuckDuckGo，不必以 Google 为唯一标准。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
