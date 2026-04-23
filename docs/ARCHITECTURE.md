# AI Learning Coach — 完整架构文档

> 版本：v2.0 | 覆盖范围：ai-service 所有功能模块的完整过程链路与数据流向

---

## 目录

1. [系统总体架构](#1-系统总体架构)
2. [中间件与请求处理栈](#2-中间件与请求处理栈)
3. [功能一：知识库上传（RAG 写入链路）](#3-功能一知识库上传rag-写入链路)
4. [功能二：RAG 问答（核心读取链路）](#4-功能二rag-问答核心读取链路)
5. [功能三：ReAct 工具 Agent](#5-功能三react-工具-agent)
6. [功能四：学习大纲生成](#6-功能四学习大纲生成)
7. [功能五：每日计划生成（LangGraph）](#7-功能五每日计划生成langgraph)
8. [功能六：RAG 质量评估（LLM-as-Judge）](#8-功能六rag-质量评估llm-as-judge)
9. [功能七：可观测性指标](#9-功能七可观测性指标)
10. [核心组件详解](#10-核心组件详解)
11. [配置项速查表](#11-配置项速查表)
12. [数据存储全景](#12-数据存储全景)
13. [高可用防护层总结](#13-高可用防护层总结)

---

## 1. 系统总体架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         前端 / Java-App / 外部调用                        │
│             Vue3(8080 → java-app) 或 直接调用 ai-service:8000             │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────────────────┐
│                      FastAPI (ai-service:8000)                            │
│                                                                           │
│  ┌─── 中间件栈（从外到内） ───────────────────────────────────────────┐   │
│  │  CORSMiddleware           跨域                                     │   │
│  │  ApiKeyAuthMiddleware     API Key 鉴权（可选，X-API-Key 头）        │   │
│  │  SlidingWindowRateLimitMiddleware  Redis 滑动窗口限流（可选）       │   │
│  │  request_id_middleware    Request-ID 注入（X-Request-ID 头）        │   │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─── API 路由 ───────────────────────────────────────────────────────┐   │
│  │  POST /api/knowledge/upload    知识库上传                           │   │
│  │  POST /api/chat                RAG 问答（SSE 流式）                 │   │
│  │  POST /api/chat/agent          ReAct Agent（非流式）                │   │
│  │  POST /api/outline/generate    学习大纲生成                         │   │
│  │  POST /api/plan/daily          每日计划（LangGraph）                │   │
│  │  POST /api/eval/rag            RAG 质量评估                         │   │
│  │  GET  /api/metrics/stats       JSON 指标                            │   │
│  │  GET  /api/metrics/prometheus  Prometheus 文本格式                  │   │
│  │  GET  /api/metrics/session/{id} Session Token 用量                  │   │
│  │  GET  /api/metrics/circuit-breaker  熔断器状态                     │   │
│  │  GET  /api/health/detail       就绪探针                             │   │
│  │  GET  /health                  存活探针                             │   │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─── 核心服务层 ──────────────────────────────────────────────────────┐   │
│  │  Guardrails   输入安全（长度/注入/有害词）                           │   │
│  │  Cache        Redis精确缓存 + Chroma语义缓存（两层短路）             │   │
│  │  RAG          BM25 + 向量混合检索 + Embedding Rerank                 │   │
│  │  Memory       Redis短期（滑动窗口）+ Chroma长期（向量检索）          │   │
│  │  LLM          ChatOpenAI → DeepSeek（重试+熔断+超时）               │   │
│  │  MCP          stdio 子进程 web_search / web_fetch                   │   │
│  │  Observability request_id + structured_log + Langfuse callbacks     │   │
│  └─────────────────────────────────────────────────────────────────────┘  │
└──────────┬─────────────────────┬────────────────────┬────────────────────┘
           │                     │                    │
    ┌──────▼──────┐      ┌───────▼───────┐   ┌───────▼──────────┐
    │    Redis     │      │   ChromaDB    │   │   DeepSeek API   │
    │  :6379       │      │   :8001       │   │  (硅基流动 Embed) │
    │ 精确缓存      │      │ 4个Collection │   │                  │
    │ 会话记忆      │      │ 笔记库        │   │                  │
    │ 限流计数      │      │ 语义缓存      │   │                  │
    │ Token配额    │      │ 长期记忆      │   │                  │
    │ 指标计数      │      │ 语义缓存      │   │                  │
    └─────────────┘      └───────────────┘   └──────────────────┘
```

---

## 2. 中间件与请求处理栈

每个 HTTP 请求的完整处理顺序（洋葱模型，从外到内）：

```
HTTP Request
    │
    ▼ [1] CORSMiddleware
        检查 Origin 头，允许所有来源（allow_origins=["*"]）
        非法来源直接拒绝，不进入后续中间件
    │
    ▼ [2] ApiKeyAuthMiddleware（默认禁用，API_KEY_ENABLED=true 后开启）
        读取 X-API-Key 请求头
        白名单路径（/health, /docs 等）直接放行
        secrets.compare_digest 常量时间比较（防时序攻击）
        失败 → AuthError(401)
    │
    ▼ [3] SlidingWindowRateLimitMiddleware（默认禁用，RATE_LIMIT_ENABLED=true 后开启）
        提取客户端 IP（X-Forwarded-For → X-Real-IP → client.host）
        计算当前时间窗口 ID = timestamp // window_size
        Redis INCR + EXPIRE（原子操作，多 Worker 安全）
        超限 → RateLimitError(429)
    │
    ▼ [4] request_id_middleware
        读取 X-Request-ID 请求头，若无则生成 UUID
        写入 contextvars（线程/协程安全，LangGraph 节点可通过 get_request_id() 读取）
        响应头中回写 X-Request-ID（便于链路追踪）
    │
    ▼ [5] 全局异常处理器（Exception Handlers）
        AppException → JSON {code, message, detail} + 对应 HTTP 状态码
        RequestValidationError → 422 + 首个字段错误的中文描述
        Exception（兜底）→ 500 + 打印完整堆栈（不暴露给客户端）
    │
    ▼ [6] 路由处理函数（API Handler）
        具体业务逻辑
    │
HTTP Response（含 X-Request-ID 头）
```

---

## 3. 功能一：知识库上传（RAG 写入链路）

**接口**：`POST /api/knowledge/upload`（multipart/form-data，仅支持 `.md` 文件）

### 完整过程链路

```
客户端上传 .md 文件
    │
    ▼ [1] 格式校验
        非 .md 文件 → HTTPException(400)
    │
    ▼ [2] 去重检查（新增）
        从 Chroma ai_learning_notes collection 查询 source=filename 的旧 chunk
        若存在旧数据 → 先 delete(ids=[...]) 清除，再导入新版本
        防止重复上传导致检索结果冗余、降低 RAG 精度
    │
    ▼ [3] 文件落盘（临时）
        保存到 data/{filename}（仅用于 LangChain Loader 读取，处理完立即删除）
    │
    ▼ [4] Markdown 加载
        UnstructuredMarkdownLoader 或 TextLoader 读取文件
        返回 List[Document]（每个 Document = 整个文件内容）
    │
    ▼ [5] 元数据注入
        doc.metadata["source"] = filename
        doc.metadata["upload_date"] = "YYYY-MM-DD"
    │
    ▼ [6] 文本切分（RecursiveCharacterTextSplitter）
        chunk_size=500, chunk_overlap=50
        切分策略：优先按 \n\n → \n → 句号/问号/感叹号 → 空格 → 字符
        产生 List[Document]（每个 Document = 1个 Chunk）
    │
    ▼ [7] 向量化 & 存储（ChromaDB）
        调用 OpenAIEmbeddings（硅基流动 bge-m3）批量 embed 所有 chunks
        写入 ai_learning_notes collection
        Chroma 自动建 HNSW 索引
    │
    ▼ [8] 临时文件清理（finally 块，成功/失败都执行）
        os.remove(file_path)
    │
    ▼ StatusResponse(success=True, message="...")
```

### 数据流向

```
.md 文件
  → TextLoader(raw_text)
  → RecursiveCharacterTextSplitter(chunk_size=500, overlap=50)
  → [Document(page_content=chunk1, metadata={source, upload_date}), ...]
  → OpenAIEmbeddings.embed_documents([chunk1_text, chunk2_text, ...])
  → [[float×1536], [float×1536], ...]
  → chromadb.HttpClient.add(embeddings, documents, metadatas, ids)
  → Chroma HNSW 索引更新
```

### ChromaDB Collection 结构

```
Collection: ai_learning_notes
  id: UUID（Chroma 自动生成）
  embedding: float[1536]（bge-m3）
  document: chunk 文本
  metadata: {
    source: "filename.md",
    upload_date: "2024-01-01"
  }
```

---

## 4. 功能二：RAG 问答（核心读取链路）

**接口**：`POST /api/chat`（返回 SSE 流式响应）

### 完整过程链路

```
POST /api/chat { question, session_id, messages? }
    │
    ▼ [1] Guardrails 输入校验（app/guardrails/input_guard.py）
        ├── 空输入检查
        ├── 长度检查：len(question) > MAX_INPUT_LENGTH(4000) → InputValidationError(400)
        ├── 有害关键词匹配（"制作炸弹"等黑名单词）
        ├── Prompt 注入正则检测（"ignore previous instructions"等8种模式）
        └── 重复字符攻击检测（单字符占比 >70% 且长度 >50）
    │
    ▼ [2] Session Token 配额检查（SESSION_TOKEN_BUDGET > 0 时生效）
        Redis GET token_budget:{session_id}
        预估输入 Token = count_tokens(question)
        已用 + 预估 > 配额 → RateLimitError(429)
    │
    ▼ [3-A] 第一层缓存：Redis 精确缓存
        normalize(question) = strip().lower().split()拼接
        key = "cache:chat:exact:{SHA256(normalized)}"
        Redis GET → 命中？返回缓存答案（命中延迟 <5ms）
        miss → 记录 metrics:cache:exact:miss
    │
    ▼ [3-B] 第二层缓存：Chroma 语义缓存（3-A miss 时执行）
        对 question 做 bge-m3 embedding
        在 semantic_qa_cache collection 中查 k=1 最近邻
        余弦距离 < SEMANTIC_CACHE_MAX_DISTANCE(0.42) → 命中（延迟 ~100ms）
        miss → 记录 metrics:cache:semantic:miss
    │
    ▼（缓存全部 miss，进入 RAG 链路）
    │
    ▼ [4] 会话记忆加载
        ├── 短期记忆：Redis LRANGE chat:session:{session_id} -20 -1
        │   获取最近 CHAT_HISTORY_MAX_TURNS(10) 轮对话
        │   format_history_block() 格式化为 history_block 字符串
        └── 长期记忆（LONG_MEMORY_ENABLED=true 时）：
            Chroma session_long_memory collection
            similarity_search(question, k=3, filter={session_id})
            注入 history_block 末尾
    │
    ▼ [5] 混合检索（app/rag/retriever.py）
        ├── BM25Retriever（关键词检索）
        │   ├── 从 Chroma 全量加载所有 documents（重建 BM25 索引，MVP 设计）
        │   ├── 使用 rank_bm25 计算 TF-IDF 相关性分数
        │   └── 返回 Top-k（k = RETRIEVAL_CANDIDATES // 2 = 6）文档
        └── VectorRetriever（语义检索）
            ├── 对 question 做 bge-m3 embedding
            ├── Chroma HNSW 近似最近邻搜索
            └── 返回 Top-k（k=6）文档
        │
        EnsembleRetriever.invoke()
        ├── 合并两路结果（去重）
        ├── 按 RRF（Reciprocal Rank Fusion）算法加权融合：BM25=0.3, 向量=0.7
        └── 返回 Top-N（合并后最多 RETRIEVAL_CANDIDATES=12 个）
    │
    ▼ [6] Embedding Rerank（RERANK_ENABLED=true 时）
        对 question 和所有候选文档做 bge-m3 embedding
        计算 query embedding 与每个文档 embedding 的余弦相似度
        按相似度降序排序，取 RERANK_TOP_N(4) 个文档
        效果：从"召回 12"精排为"精确 4"
    │
    ▼ [7] Prompt 构造（app/prompts/yaml_loader.py）
        加载 qa_{PROMPT_QA_VERSION}.yaml（v1 或 v2）
        system: 角色定义 + 回答规范
        human: "历史对话: {history_block}\n上下文: {context}\n问题: {question}"
        ChatPromptTemplate.from_messages([system, human])
    │
    ▼ [8] LCEL 链执行（app/agents/qa.py）
        _normalize_input → RunnablePassthrough.assign(context=_retrieve_and_format)
        → ChatPromptTemplate → ChatOpenAI(DeepSeek) → StrOutputParser
    │
    ▼ [9] 流式生成 + SSE 推送（带总超时）
        asyncio.wait_for(_collect_stream(), timeout=CHAT_STREAM_TIMEOUT=90s)
        收集完整答案文本后分块（chunk_size=20字符）通过 SSE 推送
        EventSourceResponse：data: {chunk}\n\n
        结束信号：event: end\n data: \n\n
        超时 → event: error\n data: 超时提示
    │
    ▼ [10] 后处理（流结束后执行）
        ├── record_tokens(tok_in, tok_out)：全局 Token 计数
        ├── record_latency(elapsed_ms)：延迟统计
        ├── _record_session_tokens(session_id, total_tokens)：Session 配额累加
        ├── append_session_message(session_id, "user", question)：短期记忆写入
        ├── append_session_message(session_id, "assistant", answer)：短期记忆写入
        ├── set_exact_cached_answer(question, answer)：写入 Redis 精确缓存（TTL=1h）
        ├── add_semantic_cache_entry(question, answer)：写入 Chroma 语义缓存
        └── index_qa_turn(session_id, question, answer)：写入 Chroma 长期记忆（可选）
    │
    └── structured_log("chat_complete", latency_ms, tokens_in, tokens_out, cache="miss")
```

### 数据流向图

```
question
  │
  ├─[精确缓存命中]──────────────────────────────────────────► SSE answer
  │   Redis GET cache:chat:exact:{SHA256}
  │
  ├─[语义缓存命中]──────────────────────────────────────────► SSE answer
  │   Chroma semantic_qa_cache similarity_search(dist < 0.42)
  │
  └─[缓存 miss]
        │
        ├── Redis LRANGE chat:session:{id}
        │     └── history_block 字符串
        │
        ├── BM25(question) + Chroma.search(embed(question), k=6)
        │     └── 12 候选 Document
        │
        ├── bge-m3.embed([q, doc1...doc12]) → 余弦相似度重排
        │     └── Top-4 Document
        │
        ├── qa_{v}.yaml → ChatPromptTemplate
        │     └── Prompt(system, history_block, context, question)
        │
        ├── DeepSeek.astream(prompt)
        │     └── token1, token2, ... → SSE data: chunks
        │
        └── 后处理写回 Redis(精确缓存) + Chroma(语义缓存+长期记忆)
```

---

## 5. 功能三：ReAct 工具 Agent

**接口**：`POST /api/chat/agent`（JSON 非流式响应）

### 完整过程链路

```
POST /api/chat/agent { question, session_id }
    │
    ▼ [1] Guardrails 输入校验（同 /chat）
    │
    ▼ [2] get_react_graph()（单例）
        create_react_agent(llm, [get_current_time, search_my_notes])
        LangGraph 预置 ReAct 图（内置循环控制）
    │
    ▼ [3] asyncio.wait_for(graph.ainvoke(), timeout=PLAN_TIMEOUT_SECONDS=120s)
        ReAct 循环（LangGraph 内部实现）：
        ┌───────────────────────────────────┐
        │  HumanMessage(question)           │
        │      ↓                            │
        │  LLM 思考（Thought）              │
        │  → 需要工具？ Yes → ToolCall      │
        │                ↓                  │
        │      工具执行（Action）            │
        │      ├── get_current_time()       │
        │      │   返回 "2024-01-01 12:00"  │
        │      └── search_my_notes(query)   │
        │           ├── BM25 检索           │
        │           └── 向量检索            │
        │           返回笔记上下文字符串     │
        │                ↓                  │
        │      ToolMessage(Observation)     │
        │          ↓                        │
        │  LLM 再思考（基于工具结果）       │
        │  → 需要更多工具？ → 继续循环      │
        │  → 足够了？→ AIMessage(最终回答)  │
        └───────────────────────────────────┘
    │
    ▼ [4] 提取最终消息
        result["messages"][-1].content → 最终回答文本
    │
    ▼ 返回 JSON:
        {
          "answer": "...",
          "session_id": "...",
          "request_id": "...",
          "tool_calls_count": N  // 实际调用工具次数
        }
```

### ReAct vs 固定 RAG 链选型对比

| 维度 | ReAct Agent (/chat/agent) | 固定 RAG 链 (/chat) |
|------|------------------------|-------------------|
| 控制流 | LLM 自主决策工具调用 | 固定 Pipeline |
| 响应格式 | JSON（非流式） | SSE 流式 |
| 工具灵活性 | 可按需调用任意工具 | 固定检索一个知识库 |
| 延迟 | 较高（多轮 LLM） | 较低（一次 LLM） |
| 适用场景 | 需要工具辅助的开放问答 | 知识库问答 |

---

## 6. 功能四：学习大纲生成

**接口**：`POST /api/outline/generate`

### 完整过程链路

```
POST /api/outline/generate { target, deadline }
    │
    ▼ [1] Guardrails：enforce_input(target)
    │
    ▼ [2] get_outline_generation_chain()（每次请求重新构建，无状态）
        ├── PydanticOutputParser(StudyOutlineResponse)
        │     生成 format_instructions（JSON Schema + 字段说明）
        ├── 系统 Prompt 拼接：
        │     outline_system_template（角色定义 + 输出规范）
        │     + format_instructions（Pydantic 生成）
        │     + few_shot_examples[0]（高质量示例，防止格式偏差）
        │   注意：花括号转义（{} → {{}}）防止 Jinja2 模板冲突
        └── ChatPromptTemplate.from_messages([system, human])
    │
    ▼ [3] asyncio.wait_for(chain.ainvoke({target, deadline}), timeout=LLM_INVOKE_TIMEOUT=60s)
        LCEL 链执行：
        ChatPromptTemplate → LLM → PydanticOutputParser
        │
        LLM 输出（JSON 字符串）：
        {
          "title": "...",
          "overview": "...",
          "chapters": [
            { "chapter_title": "...", "description": "...", "key_points": [...] }
          ]
        }
        │
        PydanticOutputParser.parse(json_string)
        → StudyOutlineResponse Pydantic 对象
    │
    ▼ 返回 StudyOutlineResponse JSON
```

### 数据流向

```
{target, deadline}
  → ChatPromptTemplate(system=role+format+example, human=target+deadline)
  → DeepSeek.ainvoke(messages)
  → raw_text (JSON 字符串)
  → PydanticOutputParser.parse()
  → StudyOutlineResponse(title, overview, chapters=[...])
  → FastAPI JSON 响应
```

---

## 7. 功能五：每日计划生成（LangGraph）

**接口**：`POST /api/plan/daily`

### 完整过程链路

```
POST /api/plan/daily { goal }
    │
    ▼ [1] get_planner_graph()（单例，应用启动时懒加载）
    │
    ▼ [2] asyncio.wait_for(graph.ainvoke({goal}), timeout=PLAN_TIMEOUT_SECONDS=120s)
    │
    LangGraph 状态机执行（PlannerState TypedDict 共享状态）：
    │
    ┌── Node 1: analyze_goal ──────────────────────────────────────────┐
    │   初始化 repair_count=0                                           │
    │   可扩展：分析目标是否需要联网/检索                                │
    └──────────────────────────────────────────────────────────────────┘
    │ Edge: analyze_goal → retrieve_notes
    ▼
    ┌── Node 2: retrieve_notes ────────────────────────────────────────┐
    │   search_my_notes.invoke({query: goal})                           │
    │   → EnsembleRetriever（BM25 + 向量，同 RAG 链路）                 │
    │   → 格式化为 notes_context 字符串                                 │
    └──────────────────────────────────────────────────────────────────┘
    │ Edge: retrieve_notes → web_research
    ▼
    ┌── Node 3: web_research ──────────────────────────────────────────┐
    │   await web_research(goal)（降级保护：失败时 ctx=""，不中断）      │
    │   └── _call_mcp_tool("web_search", {query: goal, max_results: 3})│
    │         stdio 启动 MCP Server 子进程                              │
    │         → DuckDuckGo HTML 解析，返回 [{title, url, snippet}×3]   │
    │       _call_mcp_tool("web_fetch", {url: top_url, max_chars: 4000})│
    │         域名白名单校验（防 SSRF）                                 │
    │         → 抓取页面正文（BeautifulSoup）                           │
    │   → 拼接为 web_context 字符串                                    │
    └──────────────────────────────────────────────────────────────────┘
    │ Edge: web_research → draft_plan
    ▼
    ┌── Node 4: draft_plan ────────────────────────────────────────────┐
    │   ainvoke_with_retry(DRAFT_PROMPT, timeout=LLM_INVOKE_TIMEOUT)   │
    │   三重保护：                                                      │
    │   ├── 熔断器检查（OPEN → 立即 LLMError）                          │
    │   ├── asyncio.wait_for（单次 60s 超时）                           │
    │   └── 指数退避重试（429/5xx，最多 LLM_MAX_RETRIES=3 次）          │
    │   LLM 输出 JSON 字符串 → plan_raw                                 │
    └──────────────────────────────────────────────────────────────────┘
    │ Edge: draft_plan → validate_plan
    ▼
    ┌── Node 5: validate_plan ─────────────────────────────────────────┐
    │   剥离 markdown 代码块（```json ... ```）                         │
    │   json.loads(plan_raw) → Pydantic DailyPlanResponse 校验         │
    │   成功 → plan=data, validation_error=""                           │
    │   失败 → validation_error=错误信息                                │
    └──────────────────────────────────────────────────────────────────┘
    │ Conditional Edge: _route_after_validation
    │   ├── validation_error=="" → "ok" → END
    │   ├── repair_count < 2 → "repair" → repair_plan
    │   └── repair_count >= 2（兜底） → "ok" → END（API 层报错）
    ▼（若 validation 失败）
    ┌── Node 6: repair_plan ───────────────────────────────────────────┐
    │   ainvoke_with_retry(REPAIR_PROMPT, timeout=LLM_INVOKE_TIMEOUT)  │
    │   REPAIR_PROMPT 包含：原始 plan_raw + 具体 validation_error       │
    │   LLM 修复后返回新的 plan_raw                                    │
    │   repair_count += 1                                               │
    └──────────────────────────────────────────────────────────────────┘
    │ Edge: repair_plan → validate_plan（形成修复循环，最多 2 次）
    │
    ▼（最终 State）
    plan_data = final_state["plan"] 或 None（超出修复次数时）
    │
    ▼ DailyPlanResponse(**plan_data) 或 LLMError
```

### LangGraph 状态流转图

```
START
  │
  ▼
analyze_goal ──► retrieve_notes ──► web_research ──► draft_plan
                                                          │
                                                     validate_plan
                                                    /             \
                                               ok /               \ repair_count<2
                                                 /                 \
                                               END              repair_plan
                                                                    │
                                                               validate_plan
                                                              /             \
                                                         ok /               \ ≥2次
                                                           /                 \
                                                         END                END（API报错）
```

---

## 8. 功能六：RAG 质量评估（LLM-as-Judge）

**接口**：`POST /api/eval/rag`

### 完整过程链路

```
POST /api/eval/rag { question }
    │
    ▼ [1] 执行 RAG 检索
        retrieve_and_format_docs(question) → context 字符串（Top-4 Chunks）
    │
    ▼ [2] 执行 RAG 生成
        get_qa_chain().ainvoke({question, history_block=""}) → answer 字符串
    │
    ▼ [3] 并发执行三维 LLM-as-Judge 评估（asyncio.gather）
        ├── 忠实度（Faithfulness）
        │   Judge Prompt：上下文 + 问题 + 答案 → LLM 判断答案是否完全基于上下文
        │   → score(0-1) + reason
        ├── 答案相关性（Answer Relevance）
        │   Judge Prompt：问题 + 答案 → LLM 判断答案是否切中问题
        │   → score(0-1) + reason
        └── 上下文相关性（Context Relevance）
            Judge Prompt：问题 + 上下文 → LLM 判断检索到的文档是否有用
            → score(0-1) + reason
    │
    ▼ [4] 综合评分
        overall = (faithfulness + answer_relevance + context_relevance) / 3
    │
    ▼ 返回 JSON：
        {
          "scores": {
            "faithfulness": {"score": 0.9, "reason": "..."},
            "answer_relevance": {"score": 0.8, "reason": "..."},
            "context_relevance": {"score": 0.7, "reason": "..."},
            "overall": 0.8
          },
          "interpretation": "优秀：RAG 系统运行良好"
        }
```

> ⚠️ 此接口会触发 **4 次** LLM 调用（1 次生成 + 3 次评估），
> 适合离线测试/QA 场景，**不应在生产高频接口中调用**。

---

## 9. 功能七：可观测性指标

### 指标数据写入（自动，每次请求触发）

| 写入时机 | 调用函数 | Redis Key |
|---------|---------|-----------|
| 精确缓存命中 | `_record_cache_metric("exact", hit=True)` | `metrics:cache:exact:hit` |
| 精确缓存未命中 | `_record_cache_metric("exact", hit=False)` | `metrics:cache:exact:miss` |
| 语义缓存命中 | `_record_cache_metric("semantic", hit=True)` | `metrics:cache:semantic:hit` |
| 语义缓存未命中 | `_record_cache_metric("semantic", hit=False)` | `metrics:cache:semantic:miss` |
| LLM 生成完成 | `record_tokens(tok_in, tok_out)` | `metrics:token:in:total`, `metrics:token:out:total`, `metrics:request:total` |
| 请求延迟 | `record_latency(elapsed_ms)` | `metrics:latency:sum_ms`, `metrics:latency:count` |
| 请求错误 | `record_request_error()` | `metrics:request:error` |
| Session Token | `_record_session_tokens(session_id, tokens)` | `token_budget:{session_id}` |

### 指标读取端点

```
GET /api/metrics/stats
    → Redis MGET 所有 metrics: 键
    → 计算命中率 = hit/(hit+miss)
    → 估算 Token 费用（DeepSeek 参考价格）
    → 返回 JSON

GET /api/metrics/prometheus
    → 生成 Prometheus exposition format 文本
    → Content-Type: text/plain; version=0.0.4
    → 可被 Prometheus Server 直接采集，接入 Grafana

GET /api/metrics/session/{session_id}
    → Redis GET + TTL token_budget:{session_id}
    → 返回已用/配额/剩余/窗口剩余秒数

GET /api/metrics/circuit-breaker
    → 读取进程内 llm_circuit_breaker 状态
    → CLOSED/OPEN/HALF_OPEN + 失败次数 + 冷却剩余时间

GET /api/health/detail（就绪探针）
    → Redis PING
    → Chroma collection.count()
    → 返回 {status: ok/degraded, services: {redis, chromadb}}
```

### 熔断器状态机

```
               连续失败 ≥ threshold
CLOSED ─────────────────────────────────► OPEN
  ▲                                         │
  │                                         │ 冷却 reset_timeout 秒
  │           试探成功                       ▼
  └──────────────────────────────────── HALF_OPEN
                                         │
                                         │ 试探失败
                                         ▼
                                        OPEN（重置冷却计时）
```

---

## 10. 核心组件详解

### ChromaDB 四个 Collection 职责

| Collection | 配置键 | 用途 | 写入时机 | 读取时机 |
|-----------|--------|------|---------|---------|
| `ai_learning_notes` | `CHROMA_COLLECTION_NAME` | 笔记知识库 | `POST /knowledge/upload` | RAG 检索、BM25 初始化 |
| `semantic_qa_cache` | `SEMANTIC_CACHE_COLLECTION` | 语义缓存 | chat 回答后写回 | chat 请求第二层缓存查询 |
| `session_long_memory` | `SESSION_MEMORY_COLLECTION` | 长期记忆 | chat 回答后（可选） | chat 请求历史上下文注入 |
| （内部，Chroma 管理） | - | HNSW 索引 | embed 写入时自动 | similarity_search 时 |

### Redis 数据结构全景

```
Key 模式                           数据结构    用途
──────────────────────────────────────────────────────────────────
cache:chat:exact:{SHA256}         String      精确问答缓存（TTL=CHAT_CACHE_TTL_SECONDS）
chat:session:{session_id}         List        短期会话历史（TTL=CHAT_SESSION_TTL_SECONDS）
token_budget:{session_id}         String      Session Token 用量（TTL=SESSION_TOKEN_WINDOW）
rl:aicoach:{ip}:{path}:{window}   String      限流计数器（TTL=WINDOW_SECONDS×2）
metrics:cache:exact:hit           String(int) 精确缓存命中次数（永久）
metrics:cache:exact:miss          String(int) 精确缓存未命中次数
metrics:cache:semantic:hit        String(int) 语义缓存命中次数
metrics:cache:semantic:miss       String(int) 语义缓存未命中次数
metrics:token:in:total            String(int) 累计输入 Token
metrics:token:out:total           String(int) 累计输出 Token
metrics:request:total             String(int) 累计请求数
metrics:request:error             String(int) 累计错误数
metrics:latency:sum_ms            String(float) 累计延迟（毫秒）
metrics:latency:count             String(int) 延迟采样数
```

### LLM 高可用三层防护

```
ainvoke_with_retry(messages, timeout=60s)
    │
    ▼ 第1层：熔断器检查
    │   llm_circuit_breaker.is_open()
    │   OPEN 状态 → 立即抛 LLMError（不发起请求）
    │   HALF_OPEN 状态 → 放行一次试探
    │
    ▼ 第2层：asyncio.wait_for（单次超时）
    │   timeout=LLM_INVOKE_TIMEOUT（默认60s）
    │   TimeoutError → 记录熔断失败 → 抛 TimeoutError（不重试）
    │
    ▼ 第3层：重试循环（最多 LLM_MAX_RETRIES+1 次）
        for attempt in range(1, max_attempts+1):
            try:
                result = await wait_for(llm.ainvoke(), timeout)
                circuit_breaker.record_success()
                return result
            except TimeoutError:
                raise（不重试）
            except Exception as exc:
                if not _is_retryable_error(exc): raise immediately
                circuit_breaker.record_failure()
                wait = min(max, min * 2^attempt)  # 指数退避
                await asyncio.sleep(wait)
```

---

## 11. 配置项速查表

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API Key（必填） |
| `SILICONFLOW_API_KEY` | - | 硅基流动 Embedding API Key（必填） |
| `CHROMA_MODE` | `remote` | `remote`（Docker）或 `embedded`（本地） |
| `CHROMA_HOST` | `chroma` | Chroma Server 主机名 |
| `CHUNK_SIZE` | `500` | 文档分块大小（字符数） |
| `CHUNK_OVERLAP` | `50` | 分块重叠大小 |
| `RETRIEVAL_CANDIDATES` | `12` | 混合检索召回候选数 |
| `RERANK_TOP_N` | `4` | Rerank 后保留文档数 |
| `RERANK_ENABLED` | `true` | 是否启用 Embedding Rerank |
| `CHAT_CACHE_TTL_SECONDS` | `3600` | 精确缓存过期时间（秒） |
| `SEMANTIC_CACHE_MAX_DISTANCE` | `0.42` | 语义缓存相似度阈值（越小越严格） |
| `CHAT_HISTORY_MAX_TURNS` | `10` | 短期会话保留轮次 |
| `LONG_MEMORY_ENABLED` | `false` | 是否开启长期向量记忆 |
| `PROMPT_QA_VERSION` | `v1` | QA Prompt 版本（v1/v2） |
| `MAX_INPUT_LENGTH` | `4000` | Guardrails 最大输入字符数 |
| `SESSION_TOKEN_BUDGET` | `0` | Session Token 配额（0=不限制） |
| `SESSION_TOKEN_WINDOW` | `3600` | Token 配额窗口（秒） |
| `LLM_MAX_RETRIES` | `3` | LLM 最大重试次数 |
| `LLM_INVOKE_TIMEOUT` | `60.0` | 单次 LLM 非流式调用超时（秒） |
| `PLAN_TIMEOUT_SECONDS` | `120.0` | LangGraph 计划生成总超时（秒） |
| `CHAT_STREAM_TIMEOUT` | `90.0` | 流式问答总超时（秒） |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | 熔断触发失败次数阈值 |
| `CIRCUIT_BREAKER_RESET_TIMEOUT` | `30.0` | 熔断冷却时间（秒） |
| `RATE_LIMIT_ENABLED` | `false` | 是否开启限流 |
| `RATE_LIMIT_MAX_REQUESTS` | `60` | 窗口内最大请求数 |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | 限流时间窗口（秒） |
| `API_KEY_ENABLED` | `false` | 是否开启 API Key 鉴权 |
| `API_KEYS` | `dev-key-...` | 合法 API Key（逗号分隔） |
| `LANGFUSE_PUBLIC_KEY` | `` | Langfuse 追踪 Key（空=不启用） |

---

## 12. 数据存储全景

```
用户数据流向总览：

上传 .md 文件
  └──► Chroma(ai_learning_notes)：向量化存储，永久保留

提问 /chat
  ├──► Redis(cache:chat:exact:*)：精确缓存，TTL=1h
  ├──► Chroma(semantic_qa_cache)：语义缓存，永久保留
  ├──► Redis(chat:session:*)：会话短期记忆，TTL=24h
  ├──► Chroma(session_long_memory)：长期记忆，永久保留（可选）
  ├──► Redis(token_budget:*)：Session Token 配额，TTL=1h
  └──► Redis(metrics:*)：指标计数，永久保留

提问 /chat/agent
  └──► Chroma(ai_learning_notes)：工具 search_my_notes 只读检索

生成 /plan/daily
  ├──► Chroma(ai_learning_notes)：retrieve_notes 只读检索
  └──► MCP web_search + web_fetch：实时联网检索（不持久化）

评估 /eval/rag
  └──► Chroma(ai_learning_notes)：只读检索（评估上下文）
```

---

## 13. 高可用防护层总结

```
攻击/故障类型               防护措施                             实现位置
─────────────────────────────────────────────────────────────────────────────
Prompt 注入攻击             正则规则检测                         guardrails/input_guard.py
有害内容输入                关键词黑名单                         guardrails/input_guard.py
超长输入（Token炸弹）        MAX_INPUT_LENGTH 硬限制              guardrails/input_guard.py
重复字符攻击                字符频率检测                         guardrails/input_guard.py
恶意消耗 Token             Session Token 配额（Redis INCR）       api/chat.py
接口被刷（DDoS）            滑动窗口限流（Redis INCR/EXPIRE）      middleware/rate_limit.py
未授权访问                  API Key 鉴权（常量时间比较）           middleware/auth.py
LLM API 429/5xx 故障       指数退避重试（最多3次）                core/llm.py (ainvoke_with_retry)
LLM API 持续故障            熔断器（5次失败开路，30s冷却）          core/llm.py (CircuitBreaker)
LLM 单次响应超时            asyncio.wait_for（单次60s）            core/llm.py (ainvoke_with_retry)
LLM 流式挂起               asyncio.wait_for（流式90s总超时）       api/chat.py
LangGraph 长任务超时         asyncio.wait_for（计划生成120s）       api/plan.py
Agent 无限工具调用循环       asyncio.wait_for（Agent 120s总超时）   api/chat_agent.py
Redis 不可用                fail-open（放行请求，监控告警）         多处 try/except
MCP 联网检索失败             降级为空字符串（不中断计划生成流程）    graphs/planner_graph.py
重复文件上传                先删旧数据再导入（去重检查）            api/knowledge.py
SSRF 攻击（任意 URL 抓取）   MCP web_fetch 域名白名单              tools/mcp_adapter.py
```

---

> 📄 本文档与代码同步维护。如新增功能或修改配置，请同步更新此文档对应章节。
