# AI Learning Coach｜现有实现讲解（可作面试讲稿）

本文聚焦“你现在项目里已经实现了什么、为什么这么拆、关键链路怎么跑”，并按 **面试高频** 的讲述方式组织：架构 → 核心端点 → 调用链路 → 存储与一致性 → 工程化要点 → 可演进方向。

---

## 1. 总体架构与职责边界（Java 业务编排 + Python 智能编排）

### 1.1 服务与组件
- **Java 服务 `java-app`（Spring Boot, `:8080`）**
  - 对外提供业务 API（Plan/Chat/Outline Confirm）
  - 落库（Postgres）、缓存（Redis）、容错（Resilience4j）
  - 通过 Feign/WebClient 调用 Python AI 服务
- **Python 服务 `ai-service`（FastAPI, `:8000`）**
  - LLM 调用（DeepSeek OpenAI 兼容）
  - RAG：知识上传→切分→向量化→检索→生成
  - Agent/工具调用（当前 planner 为 LangChain AgentExecutor）
  - SSE 流式输出
- **Postgres（业务数据）**：计划、任务、对话历史、大纲等
- **Redis（缓存）**：当日计划缓存
- **Chroma（向量数据库）**：笔记向量检索

### 1.2 调用拓扑

```mermaid
flowchart LR
  user[User/Client] --> javaApp[Java:java-app]
  javaApp -->|Feign POST /plan/daily| aiService[Python:ai-service]
  javaApp -->|WebClient POST /chat (SSE)| aiService
  javaApp --> postgres[(Postgres)]
  javaApp --> redis[(Redis)]
  aiService --> chroma[(Chroma VectorDB)]
  aiService --> deepseek[DeepSeek LLM/Embeddings]
```

### 1.3 这样拆的面试叙事（Why）
- **Java 侧优势**：企业级工程化（鉴权、限流、审计、事务、缓存、熔断、可观测性）与数据模型/业务聚合更成熟
- **Python 侧优势**：AI 生态（LangChain/LangGraph/MCP/评测工具）迭代快，适合承载 Prompt/RAG/Agent 编排
- **混合架构价值**：用最熟的 Java 做“稳态业务”，用 Python 做“快速演进的智能能力”，两端通过明确 API 契约协作

---

## 2. Python `ai-service`：端点 → 调用链 → 核心文件

### 2.1 服务入口与路由
- **入口**：`ai-service/main.py`
  - 注册路由：`/api/outline/*`、`/api/knowledge/*`、`/api/chat`、`/api/plan/*`
  - `/health`：容器健康检查
  - lifespan 启动阶段会预热向量库（`get_vector_store()`）

### 2.2 学习大纲生成（结构化输出）
- **端点**：`POST /api/outline/generate`
- **调用链**：
  - `app/api/outline.py`
  - `app/chains/outline_chain.py`：LCEL 链 `prompt | llm | PydanticOutputParser`
  - 模型输出强制符合 `StudyOutlineResponse`（Pydantic）
- **关键文件**：
  - `ai-service/app/chains/outline_chain.py`
  - `ai-service/app/models/schemas.py`（`StudyOutlineResponse`）
  - `ai-service/app/prompts/templates.py`（few-shot + 系统提示）
- **面试点**：
  - 结构化输出与解析失败处理
  - Few-shot Prompting
  - LCEL（LangChain Expression Language）链式组合

### 2.3 知识库上传（RAG 数据摄取）
- **端点**：`POST /api/knowledge/upload`（multipart 上传 `.md`）
- **调用链**：
  - `app/api/knowledge.py`：保存文件到 `data/`，补 metadata
  - `app/rag/loader.py`：`UnstructuredMarkdownLoader`
  - `app/rag/splitter.py`：`RecursiveCharacterTextSplitter`
  - `app/rag/vector_store.py`：写入 Chroma（embedding + persist）
- **关键文件**：
  - `ai-service/app/rag/loader.py`
  - `ai-service/app/rag/splitter.py`
  - `ai-service/app/rag/vector_store.py`
- **面试点**：
  - 摄取流水线设计：分割策略、metadata 设计、幂等与重复上传策略
  - embedding 成本控制（chunk_size/overlap）

### 2.4 RAG 问答（SSE 流式输出）
- **端点**：`POST /api/chat`（返回 SSE）
- **调用链**：
  - `app/api/chat.py`：`EventSourceResponse` 将 token chunk 逐条推送
  - `app/agents/qa.py`：LCEL RAG 链（retriever → prompt → llm → parser）
  - `app/rag/retriever.py`：混合检索 BM25 + Vector（`EnsembleRetriever`）
- **关键文件**：
  - `ai-service/app/api/chat.py`
  - `ai-service/app/agents/qa.py`
  - `ai-service/app/rag/retriever.py`
- **面试点**：
  - SSE/流式响应：背压、断线重连、chunk 协议
  - 混合检索：向量召回 + 关键词 BM25 增强
  - 引用与可追溯性：回答标注来源

### 2.5 每日计划（Agent + Tool Calling）
- **端点**：`POST /api/plan/daily`
- **当前实现调用链**：
  - `app/api/plan.py`：调用 `AgentExecutor.ainvoke`，再 `json.loads(output)`
  - `app/agents/planner.py`：`create_openai_tools_agent` + `AgentExecutor`
  - 工具集合：`app/tools/local_tools.py`（时间 + 搜索笔记） + `app/tools/mcp_adapter.py`（目前 stub）
- **关键文件**：
  - `ai-service/app/api/plan.py`
  - `ai-service/app/agents/planner.py`
  - `ai-service/app/tools/local_tools.py`
  - `ai-service/app/tools/mcp_adapter.py`
- **面试点**：
  - Tool Calling：工具选择策略、工具输出格式、失败重试
  - 输出鲁棒性：LLM 输出不是纯 JSON 时如何修复（典型线上问题）

### 2.6 模型与配置
- `ai-service/app/core/config.py`：环境变量（DeepSeek key/base、Chroma、RAG 参数）
- `ai-service/app/core/llm.py`：`ChatOpenAI` / `OpenAIEmbeddings`（DeepSeek OpenAI 兼容）
- **面试点**：多环境配置、密钥管理、模型切换策略（A/B、fallback）

---

## 3. Java `java-app`：端点 → 调用链 → 核心文件

### 3.1 今日计划（缓存 + DB + 调 AI）
- **端点**：`GET /api/plan/today?goal=...`
- **调用链**：
  - `controller/PlanController.java` → `service/PlanService.java`
  - `@Cacheable`：Redis 缓存（当前 key 仅用日期）
  - DB 查今日记录：`DailyPlanRepository.findByPlanDate(today)`
  - 若无：Feign 调 Python `POST /plan/daily` → 保存到 Postgres
  - Resilience4j：`@CircuitBreaker`，fallback 返回默认计划
- **关键文件**：
  - `java-app/.../controller/PlanController.java`
  - `java-app/.../service/PlanService.java`
  - `java-app/.../feign/AiServiceClient.java`
  - `java-app/.../entity/DailyPlan.java`、`Task.java`、`.../repository/DailyPlanRepository.java`
- **面试点**：
  - 缓存一致性与 key 设计（goal 不同但 key 相同会互相污染）
  - 事务与幂等：重复请求、缓存击穿
  - 熔断降级：fallback 策略与用户体验

### 3.2 Chat（SSE 透传 + 未来可落库）
- **端点**：`POST /api/chat`（`text/event-stream`）
- **调用链**：
  - `controller/ChatController.java` → `service/ChatService.java`
  - WebClient 调 Python `/chat` 并以 `Flux<String>` 流式返回
- **关键文件**：
  - `java-app/.../controller/ChatController.java`
  - `java-app/.../service/ChatService.java`
- **面试点**：
  - Reactor 流式处理、背压、超时与断开处理
  - 对话落库策略（流式结束后一次性写入 vs 边流边写）

### 3.3 Outline Confirm（落库）
- **端点**：`POST /api/outline/confirm`
- **调用链**：
  - `controller/OutlineController.java`（确认后写入 Postgres）
- **面试点**：领域建模（StudyOutline/Chapter/KeyPoints）、索引与查询设计

### 3.4 配置与依赖
- `java-app/src/main/resources/application.yml`
  - datasource、redis、resilience4j、`ai-service.url`
  - `spring.ai.openai.*` 已配置（但目前代码未实际使用 Spring AI）
- **面试点**：为什么 Java 侧暂不直接接 LLM（可维护性、演进速度、分层治理）

---

## 4. 当前实现的“已知坑位”（也是下一步增强方向）

### 4.1 RAG 性能与可扩展性
- `ai-service/app/rag/retriever.py` 构建 BM25 时会把 Chroma 全量取出，知识库大时慢且内存重。
- 典型优化：离线构建 BM25、增量更新、或引入 rerank（如 bge-reranker）并做 topK 控制。

### 4.2 输出鲁棒性
- `/api/plan/daily` 依赖 LLM 输出纯 JSON，实际线上常见“多输出/夹杂解释”导致解析失败。
- 典型优化：校验 + 修复回路、严格 schema、工具输出也结构化。

### 4.3 Chroma 拓扑一致性
- 需要明确“使用 remote Chroma server”还是“embedded + volume”。
- 典型面试点：多 worker/多实例下的索引一致性与持久化策略。

### 4.4 密钥与安全
- 任何 API Key 不应硬编码在 compose；应来自 `.env` / secrets。

---

## 5. 下一步演进（对齐你要做的 LangGraph + MCP）
- **LangGraph**：把 planner 从 AgentExecutor 升级为显式图（可追踪、可回放、可控重试）\n
- **MCP**：引入“联网检索/抓取”工具，让 agent/graph 能在“个人笔记不足”时做受控外部补全\n
- **评测与可观测性**：离线回放用例、指标（延迟/命中/引用/格式正确率）、tool call 审计\n

