
# --- Stage 1: Build Stage ---
# Use a specific version of the slim image for reproducibility.
FROM python:3.11.8-slim-bullseye AS builder

# Set the working directory in the container.
WORKDIR /app

# Prevent Python from writing .pyc files.
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure Python output is sent straight to the terminal without buffering.
ENV PYTHONUNBUFFERED 1

# Upgrade pip and install wheel.
RUN pip install --no-cache-dir --upgrade pip wheel

# Copy the requirements file into the container.
COPY requirements.txt .

# Create a wheelhouse for the dependencies.
# This compiles dependencies that need it, speeding up the final stage.
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# --- Stage 2: Final Stage ---
# Use the same base image for the final, lean container.
FROM python:3.11.8-slim-bullseye

WORKDIR /app

# Set the same environment variables.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy the pre-built wheels from the builder stage.
COPY --from=builder /app/wheels /wheels/

# Install the dependencies from the local wheels.
# This is faster and doesn't require network access.
RUN pip install --no-cache-dir /wheels/*

# Copy the application source code into the container.
COPY . .

# Expose the port the app will run on.
EXPOSE 8000

# Define the command to run the application.
# Using the recommended production-ready command with 4 workers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

