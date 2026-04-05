# syntax=docker/dockerfile:1

# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Install build-time system deps (gcc, libffi-dev) and compile all Python
# packages. These tools NEVER appear in the runtime image.
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev

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
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps ".[all,ris]"

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Lean runtime image: no gcc, no libffi-dev, no build tools.
# Copies only pre-built Python packages and application source from builder.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl is required by compose healthchecks; no build tools needed
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends curl

RUN groupadd -r polytool && useradd -r -g polytool -m polytool

WORKDIR /app

# Copy pre-built Python packages from builder (no gcc/libffi-dev included)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# Copy entry point scripts (uvicorn, polytool, etc.)
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY --from=builder /app/polytool ./polytool/
COPY --from=builder /app/packages ./packages/
COPY --from=builder /app/tools ./tools/
COPY --from=builder /app/services ./services/

RUN chown -R polytool:polytool /app

USER polytool

# No ENTRYPOINT or CMD — each compose service sets its own command
