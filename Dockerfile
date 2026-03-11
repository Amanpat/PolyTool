FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

COPY . /workspace

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[simtrader,studio]" \
    && pip install --no-cache-dir pytest numpy chromadb

EXPOSE 8765

CMD ["python", "-m", "polytool", "simtrader", "studio", "--host", "0.0.0.0", "--port", "8765"]
