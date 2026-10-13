# Cursor 学习示例 — Rules / Skills / MCP 动手教程

> 本目录是 **教学用配置**，可直接在本项目中练习 Cursor 提效能力。

---

## 一、你得到了什么

```
.cursor/
├── rules/                          # 规则（Agent 常驻/按文件加载）
│   ├── project-overview.mdc        # alwaysApply: 全局项目上下文
│   ├── ai-service-python.mdc       # globs: ai-service/**/*.py
│   └── mcp-integration.mdc         # globs: MCP 相关文件
├── skills/                         # 技能（按需工作流）
│   ├── add-mcp-tool/               # /add-mcp-tool
│   ├── review-ai-service/          # /review-ai-service
│   └── run-ai-service/             # /run-ai-service
├── mcp.json                        # Cursor IDE MCP 配置
├── mcp-servers/
│   └── aicoach_helper/server.py    # 自定义 MCP server（教学）
├── hooks.example.json              # Hooks 示例（可选启用）
└── LEARNING.md                     # 本文件
```

---

## 二、Rules 学习（约 10 分钟）

### 2.1 三种加载方式

| 规则文件 | 加载方式 | 何时生效 |
|----------|----------|----------|
| `project-overview.mdc` | `alwaysApply: true` | **每次对话**都注入 |
| `ai-service-python.mdc` | `globs: ai-service/**/*.py` | 打开/引用匹配文件时 |
| `mcp-integration.mdc` | `globs: 指定 MCP 路径` | 编辑 MCP 相关文件时 |

### 2.2 动手练习

**练习 A — 感受 alwaysApply**

1. 新开 Agent 对话（`Ctrl+I`）
2. 问：「这个项目有哪些服务？端口是多少？」
3. Agent 应能直接回答（来自 `project-overview.mdc`），无需你 @ 文档

**练习 B — 感受 globs 规则**

1. 打开 `ai-service/app/tools/mcp_adapter.py`
2. 问：「帮我加一个 print 调试日志」
3. Agent 应提醒你用 `[rid=...]` 格式（来自 `ai-service-python.mdc`）

**练习 C — 手动触发规则**

1. 在聊天输入 `@mcp-integration`（或规则 picker 里选）
2. 问：「应用内 MCP 和 Cursor MCP 有什么区别？」

### 2.3 查看 Rules 是否加载

- 输入框旁的 **上下文环（Context ring）** → 展开看 Rules 占用
- Customize → Rules → 可开关各条规则

---

## 三、Skills 学习（约 15 分钟）

Skills 是 **可复用工作流**，比 Rules 更长、更有步骤感。

### 3.1 本项目的 3 个 Skill

| 命令 | 用途 |
|------|------|
| `/add-mcp-tool` | 教 Agent 如何新增 MCP 工具 |
| `/review-ai-service` | 按 checklist 做 code review |
| `/run-ai-service` | 启动/验证 ai-service |

> 示例 Skills 设置了 `disable-model-invocation: true`，需 **手动输入 `/命令`** 才会加载。

### 3.2 动手练习

**练习 D — 用 Skill 做 Review**

```
/review-ai-service

请审查 @ai-service/app/tools/mcp_adapter.py 的 web_research 函数
```

观察输出是否包含 Critical / Suggestion 分级。

**练习 E — 用 Skill 学 MCP 开发**

```
/add-mcp-tool

我想在 web_research_server 里加一个 summarize_url 工具，先给我方案
```

Agent 应引用 skill 里的 checklist 和参考文件。

**练习 F — 用 Skill 启动服务**

```
/run-ai-service

帮我检查本地 ai-service 能否启动，依赖是否齐全
```

---

## 四、MCP 学习（约 20 分钟）

### 4.1 两套 MCP 别搞混

```
┌─────────────────────────────────────────────────────────┐
│  Cursor IDE MCP (.cursor/mcp.json)                      │
│  → 你在 Cursor 聊天里用的工具                              │
│  → 例：aicoach-helper 的 list_api_routes                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  应用内 MCP (ai-service/app/mcp_servers/)                │
│  → FastAPI / LangGraph 运行时调用的工具                   │
│  → 例：web_search, web_fetch                             │
└─────────────────────────────────────────────────────────┘
```

### 4.2 启用 Cursor MCP

1. 确保已安装 Python 依赖：`cd ai-service && pip install mcp`
2. Cursor → **Customize → MCP**
3. 找到 **aicoach-helper**，打开开关
4. 若失败：View → Output → 选 **MCP Logs**

### 4.3 动手练习

**练习 G — 调用自定义 MCP 工具**

在新对话中说：

```
用 aicoach-helper MCP 的 list_api_routes 工具，列出所有 API
```

**练习 H — 文件查找工具**

```
用 MCP find_file，hint=mcp，帮我定位 MCP 相关源码
```

**练习 I — 对比应用内 MCP**

在终端验证应用内 MCP（不经过 Cursor）：

```bash
cd ai-service
python -c "
import asyncio
from app.tools.mcp_adapter import _call_mcp_tool
async def main():
    r = await _call_mcp_tool('web_search', {'query': 'MCP protocol', 'max_results': 2})
    print(r)
asyncio.run(main())
"
```

### 4.4 扩展：filesystem MCP（可选）

若已安装 Node.js，可在 `mcp.json` 追加：

```json
"filesystem": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-filesystem",
    "${workspaceFolder}/ai-service"
  ]
}
```

这样 Cursor Agent 可受限访问 `ai-service/` 目录。

---

## 五、组合工作流（进阶）

### 场景：给项目加一个 MCP 工具

```
1. /add-mcp-tool                          ← Skill 加载工作流
2. @ai-service/app/mcp_servers/web_research_server.py  ← 精准上下文
3. @.cursor/rules/mcp-integration.mdc     ← 手动附加规则（可选）
4. Plan 模式先出方案 → 审完 → Build
5. /run-ai-service 验证
6. /review-ai-service 自查
```

### 场景：修 MCP 相关 bug

```
1. Debug 模式
2. @Terminals（粘贴报错）
3. @ai-service/app/tools/mcp_adapter.py
4. Agent 修复
5. 终端跑验证命令（见 run-ai-service skill）
```

---

## 六、Hooks 简介（可选）

`hooks.example.json` 展示了 **afterFileEdit** 钩子：Agent 改完文件后自动跑脚本。

启用步骤：

1. 复制为 `.cursor/hooks.json`
2. 把 command 改成真实脚本（如 `ruff format $FILE`）
3. Customize → Hooks 确认生效

Hooks 适合：自动 format、拦截危险 shell 命令、阻止读取 `.env`。

---

## 七、学习检查清单

完成以下即表示掌握基础：

- [ ] 能解释 alwaysApply vs globs 规则的区别
- [ ] 能用 `/add-mcp-tool` 让 Agent 按步骤回答
- [ ] 能在 Customize 里开关 aicoach-helper MCP
- [ ] 能区分 Cursor MCP 和应用内 MCP
- [ ] 能用 `@文件` + Agent 完成一次小改动
- [ ] 知道在 Output → MCP Logs 排错

---

## 八、下一步建议

1. **改一条 Rule**：在 `ai-service-python.mdc` 加你个人的编码偏好
2. **写一个 Skill**：比如 `/deploy-docker` 部署流程
3. **扩展 aicoach-helper**：加一个 `get_env_checklist` 工具
4. **团队共享**：把 `.cursor/rules` 和 `.cursor/skills` 提交 Git

有问题直接在 Cursor 里问：「根据 `.cursor/LEARNING.md`，帮我做练习 G」。
