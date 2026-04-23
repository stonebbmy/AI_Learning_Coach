# ARG 必须出现在第一个 FROM 之前，才对所有 FROM 有效；写在 Stage1 里无法用于下一段 FROM，会导致 NGINX_BASE_IMAGE 为空
ARG NODE_BASE_IMAGE=docker.m.daocloud.io/library/node:20-alpine
ARG NGINX_BASE_IMAGE=docker.m.daocloud.io/library/nginx:1.25-alpine
FROM ${NODE_BASE_IMAGE} AS builder

# 显式接收并清空 BuildKit/宿主机注入的代理（见 compose build args），避免 127.0.0.1:7890 在容器内 ECONNREFUSED
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
ENV http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= all_proxy=

WORKDIR /app

# 构建需要 vite 等 devDependencies；若本阶段为 production，npm ci 会省略 dev 并导致 `vite: not found`
ENV NODE_ENV=development

# 仅复制依赖声明文件，利用 Docker 层缓存（依赖未变时跳过 npm install）
# 使用 lockfile 可复现安装；代理已清空，npmmirror 应可直连
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --registry=https://registry.npmmirror.com

# 复制源码并构建
COPY . .

# 生产构建：将代理路径写入环境变量，nginx 负责把这些路径转发给后端服务
# DEV=false 时 api.ts 读取 VITE_* 变量；/proxy-java 和 /proxy-ai 由 nginx 代理
ENV VITE_JAVA_BASE=/proxy-java
ENV VITE_AI_BASE=/proxy-ai

# 用本地 vite 二进制，避免 npx 再连 registry；并清除可能写入 /root/.npmrc 的 proxy
RUN npm config delete proxy 2>/dev/null || true; npm config delete https-proxy 2>/dev/null || true; \
    node scripts/check-node.mjs && ./node_modules/.bin/vite build

# ── Stage 2: Nginx 静态服务 + 反向代理 ────────────────────────────────────────
FROM ${NGINX_BASE_IMAGE}

# 移除默认配置，注入项目自定义配置
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/app.conf

# 将 Vite 构建产物复制到 nginx 文档根目录
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
