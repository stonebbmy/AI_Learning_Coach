# 全局构建参数
ARG HTTP_PROXY
ARG HTTPS_PROXY
# 国内无法直连 Docker Hub 时，可用 DaoCloud 公共镜像：docker.m.daocloud.io/library/...
ARG JAVA_BUILD_IMAGE=docker.m.daocloud.io/library/eclipse-temurin:17-jdk-jammy
ARG JAVA_RUN_IMAGE=docker.m.daocloud.io/library/eclipse-temurin:17-jre-jammy

# --- Stage 1: Build Stage ---
FROM ${JAVA_BUILD_IMAGE} AS build

# Re-declare args for this stage.
ARG HTTP_PROXY
ARG HTTPS_PROXY

# 设置代理环境变量，使 Maven 使用代理下载依赖
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY
    
# Set the working directory.
WORKDIR /app

# Maven 使用国内镜像，避免 central 超时
COPY maven-settings.xml /root/.m2/settings.xml

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
RUN mvn clean package -DskipTests


# --- Stage 2: Final Stage ---
FROM ${JAVA_RUN_IMAGE}

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

