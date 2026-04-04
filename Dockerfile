FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r polytool && useradd -r -g polytool -m polytool

WORKDIR /app

# Install py-clob-client first for layer caching (no source code needed yet)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir py-clob-client

# Copy full project, then install all extras
COPY . .
RUN pip install --no-cache-dir ".[all,ris]"

RUN chown -R polytool:polytool /app

USER polytool

# No ENTRYPOINT or CMD — each compose service sets its own command
