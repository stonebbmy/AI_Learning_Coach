
# AI Learning Coach

## 1. 项目简介

**AI 学习转型教练 (AI Learning Coach)** 是一个为个人定制的AI学习助理系统，旨在帮助软件工程师（尤其是Java后端背景）高效地转型为AI应用开发工程师。

本项目作为一个完整的、可部署的MVP（最小可行产品），通过混合微服务架构，深度集成了当前AI应用开发领域最核心、最高频的面试考点技术，包括：

-   **结构化输出 (Structured Output)**: 使用 `PydanticOutputParser` 保证LLM输出的稳定性和可靠性。
-   **智能体与工具调用 (Agent & Tool Calling)**: 构建能够思考并使用外部工具（如数据库检索、实时API）的智能体。
-   **检索增强生成 (RAG)**: 实现完整的RAG链路，结合向量检索与关键字检索，提供基于个人知识库的精准问答。
-   **流式响应 (Streaming)**: 提供类似ChatGPT的打字机流式输出效果，优化用户体验。
-   **服务编排与工程化**: 使用Java + Python混合微服务架构，通过Docker Compose一键编排，并集成熔断、缓存、健康检查等生产级实践。

## 2. 架构图

```mermaid
graph TD
    subgraph "用户端 (Browser/Client)"
        UserClient[User Client]
    end

    subgraph "Docker 环境 (ai-coach-net)"
        subgraph "Java 业务服务 (Port 8080)"
            direction LR
            JavaController[API Controllers] --> JavaService[Service Layer]
            JavaService -- "JPA" --> Postgres[(PostgreSQL)]
            JavaService -- "Spring Cache" --> Redis[(Redis)]
            JavaService -- "OpenFeign / WebClient" --> AIService[Python AI Service]
        end

        subgraph "Python AI 服务 (Port 8000)"
            direction LR
            AIService[FastAPI Endpoints] --> CoreLogic[Agents / Chains / RAG]
            CoreLogic -- "LLM Calls" --> DeepSeekAPI[<-- DeepSeek API -->]
            CoreLogic -- "Vector Search" --> ChromaDB[(ChromaDB)]
        end

        Postgres -- "业务数据持久化"
        Redis -- "计划缓存"
        ChromaDB -- "笔记向量化存储"
    end

    UserClient -- "HTTP API Calls" --> JavaController
```

## 3. 技术栈清单

| 服务 / 组件 | 主要技术 |
| :--- | :--- |
| **Java 业务服务** | Java 17, Spring Boot 3, Spring AI, Spring Data JPA, OpenFeign, Resilience4j, Spring Cache, WebClient |
| **Python AI 服务** | Python 3.11, FastAPI, LangChain, Pydantic, `langchain-openai` (for DeepSeek), ChromaDB, BM25 |
| **数据库** | PostgreSQL (业务数据), Redis (缓存), Chroma (向量数据) |
| **编排与部署** | Docker, Docker Compose |
| **API 文档** | SpringDoc OpenAPI (Java), Swagger UI (FastAPI) |

## 4. 启动方式

**前提**:
-   已安装 Docker 和 Docker Compose。
-   在项目根目录创建 `.env` 文件。

**步骤**:

1.  **配置 API Key**:
    在项目根目录创建一个名为 `.env` 的文件，并填入你的 DeepSeek API Key：
    ```
    DEEPSEEK_API_KEY=your_actual_deepseek_api_key
    ```

2.  **一键启动所有服务**:
    在项目根目录运行以下命令：
    ```bash
    docker-compose up --build -d
    ```
    `--build` 参数会强制重新构建镜像，第一次启动时是必需的。`-d` 参数使服务在后台运行。

3.  **访问服务**:
    -   **Java API (Swagger)**: `http://localhost:8080/swagger-ui.html`
    -   **Python API (Swagger)**: `http://localhost:8000/docs`
    -   **PostgreSQL**: 可通过 `localhost:5432` 连接
    -   **Redis**: 可通过 `localhost:6379` 连接

4.  **停止服务**:
    ```bash
    docker-compose down
    ```

## 5. MVP 功能列表

### 已实现功能

-   [x] **学习大纲生成**: (Python: `POST /api/outline/generate`, Java: `POST /api/outline/confirm`)
    -   输入目标和期限，AI生成结构化的学习大纲。
-   [x] **知识库上传**: (Python: `POST /api/knowledge/upload`)
    -   上传Markdown笔记，自动切分、向量化并存入ChromaDB。
-   [x] **RAG 问答**: (Java: `POST /api/chat`)
    -   基于个人知识库进行问答，支持流式输出和答案来源标注。
-   [x] **每日计划生成**: (Java: `GET /api/plan/today`)
    -   AI Agent根据今日目标，结合笔记内容，生成可执行的任务清单。
-   [x] **服务容错与缓存**:
    -   对AI服务的调用实现了熔断降级。
    -   当日计划实现了Redis缓存。

### Roadmap (暂缓功能)

-   [ ] **前端界面**: 开发一个React或Vue前端，提供完整的用户交互体验。
-   [ ] **对话历史记忆**: 为RAG问答增加基于`session_id`的短期记忆能力。
-   [ ] **主动学习提醒**: 基于学习计划和进度，通过邮件或Webhook发送每日学习提醒。
-   [ ] **更复杂的Agent**: 引入`ReAct`或更复杂的Agent框架，处理多步、更开放的任务。
-   [ ] **知识图谱**: 结合知识图谱进行RAG，提供更精准和富有关联性的答案。
-   [ ] **真实MCP集成**: 对接一个真实的MCP Server，动态加载和使用外部工具。
