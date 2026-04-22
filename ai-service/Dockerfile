# 构建期：默认「兜底」—— DaoCloud 基础镜像、清华 Debian/apt、清华 PyPI；pip wheel 层不使用代理，避免经 Clash 访问 pypi.org 的 SSLEOF。
# 运行时仍由 compose 注入 HTTP_PROXY 访问外网（业务、MCP 等）。
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG PYTHON_BASE_IMAGE=docker.m.daocloud.io/library/python:3.11.8-slim-bullseye
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

FROM ${PYTHON_BASE_IMAGE} AS builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST

ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# apt：换清华 Debian 源 + 本层不走路径，避免代理+官方 deb 超时
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
      sed -i 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
    fi; \
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates; \
    update-ca-certificates; \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip --version

COPY requirements.txt .

# pip：清华索引 + 取消代理，直连国内 PyPI；wheel 仍可能从 files.pythonhosted 直连下载
RUN export PIP_INDEX_URL="$PIP_INDEX_URL" PIP_TRUSTED_HOST="$PIP_TRUSTED_HOST"; \
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true; \
    python -m pip wheel --retries 15 --timeout 300 --wheel-dir /app/wheels -r requirements.txt


ARG PYTHON_BASE_IMAGE=docker.m.daocloud.io/library/python:3.11.8-slim-bullseye
FROM ${PYTHON_BASE_IMAGE}

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    TIKTOKEN_CACHE_DIR=/app/.tiktoken

COPY --from=builder /app/wheels /wheels/

RUN python -m pip install /wheels/*

RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); print('tiktoken cache warmed')" || true

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
