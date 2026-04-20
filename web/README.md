# AI Learning Coach 前端（Vue 3 + Vite）

与当前后端能力对齐：

| 页面 | 说明 |
|------|------|
| `/outline` | `POST` Python `/api/outline/generate`，确认后 `POST` Java `/api/outline/confirm` |
| `/knowledge` | `POST` Python `/api/knowledge/upload`（`.md`） |
| `/chat` | `POST` Java `/api/chat`（SSE 流式，经 Java 转发 Python） |
| `/plan` | `GET` Java `/api/plan/today?goal=...` |

## 环境要求

- **Node.js 18 LTS 或 20 LTS**（推荐）。若使用 **Node 14 / 旧版 16**，运行 `npm run dev` 可能出现 `Unexpected token '||='`，这是 **Node 过旧** 无法解析现代语法，与项目代码无关。
- 已提供 `web/.nvmrc`（内容为 `20`）。若使用 [nvm-windows](https://github.com/coreybutler/nvm-windows)：在 `web` 目录执行 `nvm install 20` → `nvm use 20`，再 `npm install`。
- `npm run dev` / `build` 前会执行 `scripts/check-node.mjs`；版本过低会直接提示并退出。

## 本地开发

1. 启动后端：`docker compose up -d`（或分别启动 Java :8080、AI :8000）。
2. 安装依赖并启动：

```bash
cd web
npm install
npm run dev
```

浏览器访问 <http://localhost:5173>。开发模式下通过 Vite 代理访问后端（见 `vite.config.ts` 中 `/proxy-java`、`/proxy-ai`），无需额外配置跨域。

## 生产构建 / 直连后端

```bash
npm run build
```

构建产物在 `web/dist`。若静态资源与后端不同源，可设置环境变量并自行部署 Nginx 等：

- `VITE_JAVA_BASE`：例如 `http://localhost:8080`
- `VITE_AI_BASE`：例如 `http://localhost:8000/api`

（已在 `ai-service` 与 `java-app` 中开启 CORS，便于浏览器直连。）
