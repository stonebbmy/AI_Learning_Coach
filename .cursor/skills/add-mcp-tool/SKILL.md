---
name: add-mcp-tool
description: 在 AI Learning Coach 项目中新增 MCP 工具（应用内 FastMCP server 或 Cursor IDE MCP）。用户提到添加 MCP 工具、web_search、web_fetch、MCP adapter 时使用。
disable-model-invocation: true
---

# 新增 MCP 工具

## 先判断类型

| 用户意图 | 改哪里 |
|----------|--------|
| Agent 运行时调用的工具 | `ai-service/app/mcp_servers/` + `mcp_adapter.py` |
| Cursor IDE 里 Agent 用的工具 | `.cursor/mcp-servers/` + `.cursor/mcp.json` |

## 应用内 MCP 工作流

复制 checklist 并逐项完成：

```
- [ ] Step 1: 在 server 定义 @mcp.tool()
- [ ] Step 2: 在 mcp_adapter 注册
- [ ] Step 3: 在 Agent 节点或 get_mcp_tools() 暴露
- [ ] Step 4: 手动验证
```

### Step 1: 定义 Server 工具

参考 `@ai-service/app/mcp_servers/web_research_server.py`：

```python
@mcp.tool()
async def my_tool(arg: str, limit: int = 5) -> dict:
    """一句话说明工具用途。Returns: {...}"""
    limit = max(1, min(int(limit), 10))  # 始终 clamp 参数
    ...
    return {"result": "..."}
```

### Step 2: 注册到 adapter

在 `mcp_adapter.py`：

1. 如需高层 helper，加 `async def my_helper(...)` 调用 `_call_mcp_tool("my_tool", {...})`
2. 如需 LangChain Tool，在 `get_mcp_tools()` 追加 `Tool(name="mcp_my_tool", ...)`

### Step 3: 暴露给 Agent

- LangGraph 节点：直接 `await my_helper(...)`
- ReAct Agent：确保 `get_mcp_tools()` 被加载

### Step 4: 验证

```bash
cd ai-service
python -c "
import asyncio
from app.tools.mcp_adapter import _call_mcp_tool
async def main():
    r = await _call_mcp_tool('web_search', {'query': 'python asyncio', 'max_results': 2})
    print(r)
asyncio.run(main())
"
```

## Cursor IDE MCP 工作流

1. 在 `.cursor/mcp-servers/<name>/server.py` 写 FastMCP server
2. 在 `.cursor/mcp.json` 注册 server
3. Cursor → Customize → MCP → 开启并测试

详细配置见 [reference.md](reference.md)

## 反模式

- ❌ 在 server 和 adapter 重复实现同一逻辑
- ❌ fetch 类工具跳过域名白名单
- ❌ 返回无界长文本（必须 max_chars 截断）
- ❌ MCP tool 名与 LangChain tool 名混用同一字符串
