# 构建期兜底：DaoCloud 基础镜像、清华 Ubuntu apt、阿里云 Maven Central；apt/mvn 层不使用代理以免超时
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG JAVA_BUILD_IMAGE=docker.m.daocloud.io/library/eclipse-temurin:17-jdk-jammy
ARG JAVA_RUN_IMAGE=docker.m.daocloud.io/library/eclipse-temurin:17-jre-jammy

FROM ${JAVA_BUILD_IMAGE} AS build

ARG HTTP_PROXY
ARG HTTPS_PROXY

ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY

WORKDIR /app

COPY maven-settings.xml /root/.m2/settings.xml

RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list; \
      sed -i 's|http://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list; \
    fi; \
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates maven; \
    update-ca-certificates; \
    rm -rf /var/lib/apt/lists/*

COPY pom.xml .

RUN unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true; \
    mvn dependency:go-offline

COPY src ./src

RUN unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true; \
    mvn clean package -DskipTests


ARG JAVA_RUN_IMAGE=docker.m.daocloud.io/library/eclipse-temurin:17-jre-jammy
FROM ${JAVA_RUN_IMAGE}

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list; \
      sed -i 's|http://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list; \
    fi; \
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    update-ca-certificates; \
    rm -rf /var/lib/apt/lists/*

ARG JAR_FILE=target/*.jar

COPY --from=build /app/${JAR_FILE} app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
