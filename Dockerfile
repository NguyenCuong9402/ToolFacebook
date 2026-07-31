# ===============================
# Stage 1: Build Frontend
# ===============================
FROM node:22 AS frontend-builder

WORKDIR /codebase

COPY . .

WORKDIR /codebase/frontend

RUN chmod +x app_build.sh

RUN npm install
RUN npm run djangobuild

# ===============================
# Stage 2: Build Backend
# ===============================
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

# Omit development dependencies
ENV UV_NO_DEV=1

# Install system dependencies
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get clean && apt-get update \
    && rm -rf /var/lib/apt/lists/*
 
# Set the working directory
WORKDIR /codebase

COPY pyproject.toml uv.lock requirements.txt ./

# First sync dependencies from lock file
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . .

# Sync all dependencies including project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# 👇 copy frontend build artifacts
COPY --from=frontend-builder /codebase/static /codebase/static
COPY --from=frontend-builder /codebase/templates /codebase/templates

# ===============================
# Stage 3: Final Image
# ===============================
FROM python:3.13-slim-bookworm

WORKDIR /codebase

# Copy the application from the builder
COPY --from=builder /codebase /codebase

# Make the virtual environment accessible
ENV PATH="/codebase/.venv/bin:$PATH"

RUN python manage.py collectstatic --noinput

EXPOSE 5000

CMD ["gunicorn", "codebase.wsgi", "-b:8000", "-w 2"]
