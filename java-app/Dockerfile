
# --- Stage 1: Build Stage ---
# Use a Maven image with Java 17 to build the application.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Set the working directory.
WORKDIR /app

# Copy the Maven project file.
COPY pom.xml .

# Download all dependencies. This creates a cache layer in Docker.
RUN mvn dependency:go-offline

# Copy the source code.
COPY src ./src

# Package the application, skipping tests for faster builds.
RUN mvn package -DskipTests


# --- Stage 2: Final Stage ---
# Use a lightweight JRE image for the runtime.
FROM eclipse-temurin:17-jre-jammy

WORKDIR /app

# Argument to specify the JAR file name
ARG JAR_FILE=target/*.jar

# Copy the executable JAR from the build stage to the final image.
COPY --from=build /app/${JAR_FILE} app.jar

# Expose the port the application will run on.
EXPOSE 8080

# The command to run the application when the container starts.
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

