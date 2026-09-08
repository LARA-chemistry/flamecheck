#  production Dockerfile
# A qualitative analysis submission system for students in chemistry.
# to build the docker image, call :
# docker build -f Dockerfile.dev -t my_project/-dev:0.0.1 .
# docker run -p 8000:8000 --name -dev my_project/-dev:0.0.1 
# see also https://snyk.io/blog/best-practices-containerizing-python-docker/
# s. https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile
# s. https://github.com/ArjanCodes/examples/tree/main/2025/efficient-python-dockerfile

# to get the digest (=sha fingerprint) run:
# docker images --digests | grep python

ARG PYTHON_VERSION=3.13
ARG BASE_LAYER=bookworm

# add correct path to build image here ...
FROM python:${PYTHON_VERSION}-slim AS build_image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/ 
# to minimize image size one could build like (https://mherman.org/presentations/dockercon-2018/#39):
# using wheels


ENV LANG=C.UTF-8\
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1\
    UV_COMPILE_BYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=${PYTHON_VERSION} \
    PROJECT_ROOT=/opt/
ENV UV_PROJECT_ENVIRONMENT=${PROJECT_ROOT}/.venv 

# Debian package caching
ARG APT_PROXY
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${PROJECT_ROOT}

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev

# Alpine generated some very strange errors, since it was not handling cython based binary packages correctly
FROM python:${PYTHON_VERSION}-slim AS final_image
ARG PYTHON_VERSION=3.13

LABEL maintainer="mark doerr <mark.doerr@uni-greifswald.de>"
LABEL version="0.0.0"
LABEL description=" - A qualitative analysis submission system for students in chemistry. (production)"

ENV LANG=C.UTF-8\
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1\
    UV_COMPILE_BYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PROJECT_ROOT=/opt/
ENV UV_PROJECT_ENVIRONMENT=${PROJECT_ROOT}/.venv 


# Create non-root user 'appuser' for security BEFORE setting workdir
# some base image allow the --disabled-login flag
# remove set -x for production images (it is only for debugging)
RUN set -x \
    && adduser appuser \
    && groupadd -r appuser && useradd -r -g appuser appuser -m -d /home/appuser
    #--disabled-password  --no-create-home --gecos "" 

WORKDIR ${PROJECT_ROOT}

# Set working directory and change ownership
# Copy the environment, but not the source code
COPY --from=build_image --chown=appuser:appuser ${PROJECT_ROOT} .
# copy the entrypoint script
COPY --chown=appuser:appuser entrypoint.production.sh entrypoint.production.sh
RUN chmod +x entrypoint.production.sh

RUN chown -R appuser:appuser ${PROJECT_ROOT}

# set the PATH to include the virtual environment
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

USER appuser

# Expose the port the app runs on

# This is not strictly required when using docker-compose, but it is a good practice to document the port
# and it allows to run the container without docker-compose
# If you change the port, make sure to update the docker-compose.yml file accordingly
# This is the port for the uvicorn server, change if needed

EXPOSE 8000

# Set the entrypoint to the production script
# This script can be used to run the application in production mode
CMD [ "entrypoint.production.sh" ]
