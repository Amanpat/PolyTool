FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY services/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy packages
COPY packages /app/packages

# Copy service code
COPY services/api /app/services/api

# Set Python path
ENV PYTHONPATH=/app/packages:/app

WORKDIR /app/services/api

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
