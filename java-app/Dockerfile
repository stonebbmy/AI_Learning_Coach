# 全局构建参数
ARG HTTP_PROXY
ARG HTTPS_PROXY

# --- Stage 1: Build Stage ---
# Avoid Docker Hub in restricted networks: use Microsoft container registry.
FROM mcr.microsoft.com/openjdk/jdk:17-ubuntu AS build

# Re-declare args for this stage.
ARG HTTP_PROXY
ARG HTTPS_PROXY

# 设置代理环境变量，使 Maven 使用代理下载依赖
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY
    
# Set the working directory.
WORKDIR /app

# Install Maven (and CA certs) via apt.
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' \
      /etc/apt/sources.list \
    && http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates maven \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the Maven project file.
COPY pom.xml .

# Download all dependencies. This creates a cache layer in Docker.
RUN mvn dependency:go-offline

# Copy the source code.
COPY src ./src

# Package the application, skipping tests for faster builds.
RUN mvn package -DskipTests


# --- Stage 2: Final Stage ---
# Runtime stage: keep the same base to avoid extra pulls.
FROM mcr.microsoft.com/openjdk/jdk:17-ubuntu

WORKDIR /app

# Healthcheck in docker-compose uses curl; install it here (use TUNA mirror for reliability).
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' \
      /etc/apt/sources.list \
    && http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Argument to specify the JAR file name
ARG JAR_FILE=target/*.jar

# Copy the executable JAR from the build stage to the final image.
COPY --from=build /app/${JAR_FILE} app.jar

# Expose the port the application will run on.
EXPOSE 8080

# The command to run the application when the container starts.
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

