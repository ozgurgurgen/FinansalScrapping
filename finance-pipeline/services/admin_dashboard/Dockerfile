FROM python:3.12-slim

WORKDIR /app

# System deps (docker-py needs libffi)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Install deps
COPY services/admin_dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared models and service code
COPY shared_db /app/shared_db
COPY services/admin_dashboard /app

EXPOSE 3000

CMD ["python", "main.py"]
