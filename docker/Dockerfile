# Production Dockerfile for FlameCheck.
#
# A qualitative analysis submission system for students in chemistry.
#
# The image is built from the repository root (the default build context used
# by docker/docker-compose.dev-full.yaml and by CI). It:
#   1. builds the Vue/Vite frontend (frontend/dist) in a node stage,
#   2. installs the Python project + dependencies with uv in a build stage.
#      The workspace packages (flamecheck, users, substances, analyses, config)
#      are installed *editable*, so the source must be present in /opt at that
#      point — this makes the editable .pth files point at /opt/... which is the
#      same layout in the final image, so imports resolve correctly at runtime.
#   3. assembles a slim final image with the source, the built frontend, the
#      virtualenv and the production entrypoint (migrate + collectstatic + gunicorn).
#
# The application serves the built SPA from frontend/dist via WhiteNoise
# (see src/flamecheck/settings/base.py: STATICFILES_DIRS).
#
# Build:
#   docker build -f docker/Dockerfile -t flamecheck:0.0.1 .
#   docker run -p 8000:8000 --env-file .env flamecheck:0.0.1
#
# s. https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile
# s. https://snyk.io/blog/best-practices-containerizing-python-docker/

ARG PYTHON_VERSION=3.13
# Full Node version (must satisfy the NPM_VERSION engine requirement: npm 11
# needs node ^20.17.0 || >=22.9.0). Keep in sync with .gitlab-ci.yml.
ARG NODE_VERSION=22.23.3
# npm that generated frontend/package-lock.json. Aligning the build npm avoids
# the optional-deps bug (npm/cli#4828) that drops rolldown's native binding.
ARG NPM_VERSION=11.19.0

# --- Stage 1: build the frontend -------------------------------------------
FROM node:${NODE_VERSION}-alpine AS frontend_build
WORKDIR /app
# Install dependencies from the lockfile first (better layer caching).
COPY frontend/package.json frontend/package-lock.json* ./
# Use the npm version that produced the lockfile, then install from it.
RUN npm install -g "npm@${NPM_VERSION}" \
 && npm ci --no-audit --no-fund \
 && (find node_modules/@rolldown -name "rolldown-binding.linux-x64-*.node" 2>/dev/null | grep -q . \
      || (echo "rolldown binding missing; clean reinstall" \
          && rm -rf node_modules package-lock.json \
          && npm install --no-audit --no-fund))
# Build the SPA. Vite outputs to frontend/dist (see the "build" script).
COPY frontend/ ./
RUN npm run build

# --- Stage 2: build the Python project with uv -----------------------------
# The source is copied into /opt BEFORE `uv sync` so the editable installs of
# the workspace packages point at /opt/... (present in the final image too).
FROM python:${PYTHON_VERSION}-slim AS build_image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=${PYTHON_VERSION} \
    UV_PROJECT_ENVIRONMENT=/opt/.venv
ARG APT_PROXY
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential gcc curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
# Source must be present for editable installs to reference /opt paths.
# README.md / LICENSE are read by the build backend (uv_build) when the
# project itself is built, so they must be present in this stage.
COPY src/ src/
COPY packages/ packages/
COPY pyproject.toml uv.lock README.md LICENSE ./
# Install dependencies (lockfile-first for caching), then the project itself.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev

# --- Stage 3: final runtime image ------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS final_image
LABEL maintainer="mark doerr <mark.doerr@uni-greifswald.de>"
LABEL version="0.0.0"
LABEL description="FlameCheck - A qualitative analysis submission system for students in chemistry. (production)"

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PROJECT_ROOT=/opt \
    UV_PROJECT_ENVIRONMENT=/opt/.venv \
    DJANGO_SETTINGS_MODULE=flamecheck.settings.production

# Create a non-root user for security.
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /opt/staticfiles /opt/db /opt/media \
    && chown -R appuser:appuser /opt

WORKDIR /opt

# Copy the Python virtualenv + project metadata from the build stage. The
# editable .pth files inside .venv point at /opt/src and /opt/packages/...,
# which we copy next — so they resolve at runtime.
COPY --from=build_image --chown=appuser:appuser /opt/.venv /opt/.venv
COPY --chown=appuser:appuser src/ src/
COPY --chown=appuser:appuser packages/ packages/
COPY --chown=appuser:appuser manage.py pyproject.toml uv.lock ./
# Copy the built frontend so Django can serve it via WhiteNoise.
COPY --from=frontend_build --chown=appuser:appuser /app/dist frontend/dist
# Copy the production entrypoint.
COPY --chown=appuser:appuser docker/entrypoint.production.sh entrypoint.production.sh
RUN chmod +x entrypoint.production.sh

ENV PATH="/opt/.venv/bin:$PATH"
USER appuser

EXPOSE 8000

# SQLite database lives in /opt/db (a volume target for compose).
ENV DATABASE_URL=sqlite:////opt/db/db.sqlite3

# Absolute path: exec-form CMD resolves the binary against PATH, and the
# entrypoint lives in /opt (the working directory), which is not on PATH.
CMD ["/opt/entrypoint.production.sh"]
