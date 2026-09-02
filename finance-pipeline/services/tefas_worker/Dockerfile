FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY services/tefas_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared_db
COPY shared_db /app/shared_db

# Copy service code
COPY services/tefas_worker /app

EXPOSE 8001

CMD ["python", "main.py"]
