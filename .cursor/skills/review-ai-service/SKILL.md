---
name: review-ai-service
description: 审查 ai-service Python 代码变更的质量、安全与架构一致性。用户要求 code review、审查 PR、或修改了 ai-service 下的 Python 文件时使用。
disable-model-invocation: true
---

# ai-service Code Review

## 审查顺序

1. **正确性** — 逻辑、边界条件、async 用法
2. **安全** — API Key 泄露、URL 白名单、输入校验（Guardrails）
3. **架构** — 是否违反分层（api → agents/chains → core/rag/memory）
4. **可观测** — request_id、错误日志、指标
5. **测试** — 是否有可运行的验证路径

## Checklist

```
- [ ] 无硬编码密钥或 .env 真实值
- [ ] 新 env 变量已更新 .env.example
- [ ] MCP fetch 走 _is_allowed_url
- [ ] LLM 调用走 app/core/llm.py（含重试/熔断）
- [ ] 缓存键含 user/session 维度（如适用）
- [ ] Pydantic schema 与 API 文档一致
- [ ] 无 print 调试残留（应用 rid 前缀的 print 除外）
```

## 反馈格式

- 🔴 **Critical**：必须修复（安全、数据丢失、生产不可用）
- 🟡 **Suggestion**：建议改进（可读性、性能、可维护性）
- 🟢 **Nice to have**：可选优化

## 输出模板

```markdown
## Review 摘要
<1-2 句总体评价>

## Critical
- ...

## Suggestion
- ...

## 验证建议
<应运行的命令或手动测试步骤>
```

## 重点关注模块

| 模块 | 审查要点 |
|------|----------|
| `app/agents/` | 工具调用循环、token 预算、prompt 注入 |
| `app/rag/` | 检索参数、rerank、空结果处理 |
| `app/tools/mcp_adapter.py` | 白名单、结果归一化、超时 |
| `app/middleware/` | 限流 key、鉴权头 |
| `app/prompts/` | 版本号、YAML 加载路径 |
