# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev curl

RUN groupadd -r polytool && useradd -r -g polytool -m polytool

WORKDIR /app

# Layer 1: dependency manifests only — changes rarely
COPY pyproject.toml ./

# Layer 2: install ALL dependencies (cached unless pyproject.toml changes)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install ".[all,ris]"

# Layer 3: copy source code (changes often, but deps are cached above)
COPY polytool/ ./polytool/
COPY packages/ ./packages/
COPY tools/ ./tools/
COPY services/ ./services/

# Re-install with --no-deps so package entry points and metadata are correct
# (setuptools needs pyproject.toml + source to resolve entry points)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps ".[all,ris]"

RUN chown -R polytool:polytool /app

USER polytool

# No ENTRYPOINT or CMD — each compose service sets its own command
