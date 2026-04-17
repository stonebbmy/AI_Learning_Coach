# 全局构建参数，用于接收外部传入的代理地址
ARG HTTP_PROXY
ARG HTTPS_PROXY
# 可选：pip 镜像与可信 host（国内网络更稳定）
ARG PIP_INDEX_URL=http://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
# --- Stage 1: Build Stage ---
# Use a specific version of the slim image for reproducibility.
FROM python:3.11.8-slim-bullseye AS builder

# Re-declare build args for this stage (required for expansion).
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST

# 将构建参数设置为环境变量，使得 pip 等工具自动使用代理
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=100

# Set the working directory in the container.
WORKDIR /app

# Prevent Python from writing .pyc files.
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure Python output is sent straight to the terminal without buffering.
ENV PYTHONUNBUFFERED 1

# Install CA certificates for HTTPS downloads.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Sanity check pip (avoid unnecessary network upgrade here).
RUN python -m pip --version

# Copy the requirements file into the container.
COPY requirements.txt .

# Create a wheelhouse for the dependencies.
# This compiles dependencies that need it, speeding up the final stage.
RUN python -m pip wheel --wheel-dir /app/wheels -r requirements.txt


# --- Stage 2: Final Stage ---
# Use the same base image for the final, lean container.
FROM python:3.11.8-slim-bullseye

ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST

WORKDIR /app

# Set the same environment variables.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    TIKTOKEN_CACHE_DIR=/app/.tiktoken

# Copy the pre-built wheels from the builder stage.
COPY --from=builder /app/wheels /wheels/

# Install the dependencies from the local wheels.
# This is faster and doesn't require network access.
RUN python -m pip install /wheels/*

# Best-effort warmup: pre-download tiktoken encoding cache.
# (Do not fail the build if network is unavailable.)
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); print('tiktoken cache warmed')" || true

# Copy the application source code into the container.
COPY . .

# Expose the port the app will run on.
EXPOSE 8000

# Define the command to run the application.
# Using the recommended production-ready command with 4 workers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

