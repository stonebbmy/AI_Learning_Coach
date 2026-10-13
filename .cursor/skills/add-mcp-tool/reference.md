# MCP 配置参考

## .cursor/mcp.json 结构

```json
{
  "mcpServers": {
    "server-id": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {
        "API_KEY": "${env:MY_API_KEY}"
      }
    }
  }
}
```

### 变量插值

| 变量 | 含义 |
|------|------|
| `${workspaceFolder}` | 当前工作区根目录 |
| `${env:NAME}` | 系统环境变量 |

## 本项目已配置的 Server

### aicoach-helper（自定义，教学用）

- 路径：`.cursor/mcp-servers/aicoach_helper/server.py`
- 工具：`list_api_routes`、`get_architecture_summary`
- 无需 API Key，开箱即用

### filesystem（可选，需 Node.js）

取消 `mcp.json` 中注释即可启用，限制 Agent 只能访问 `ai-service/` 目录。

## 排错

1. **Server 不显示**：Customize → MCP → 刷新；检查 JSON 语法
2. **启动失败**：Output 面板 → MCP Logs
3. **Python 找不到 mcp 包**：在 ai-service 虚拟环境中 `pip install mcp`，或设置 `PYTHONPATH`

## 与应用内 MCP 对比

```
Cursor Agent 聊天
    ↓ 调用
.cursor/mcp.json 配置的 server（IDE 级）

FastAPI / LangGraph 运行时
    ↓ 调用
ai-service/app/mcp_servers/（应用级）
```

两者独立，可复用相同的 FastMCP 写法，但部署和调用方不同。
