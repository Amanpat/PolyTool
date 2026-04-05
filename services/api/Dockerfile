# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends curl

WORKDIR /app

# Install dependencies (cached unless requirements.txt changes)
COPY services/api/requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy packages
COPY packages /app/packages

# Copy service code
COPY services/api /app/services/api

# Set Python path
ENV PYTHONPATH=/app/packages:/app

WORKDIR /app/services/api

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
