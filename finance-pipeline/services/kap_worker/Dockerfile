FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy kap-pipeline code
COPY kap-pipeline /app/kap-pipeline
COPY shared_db /app/shared_db
COPY services/kap_worker/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt
RUN pip install --no-cache-dir -r /app/kap-pipeline/requirements.txt

EXPOSE 8002

CMD ["python", "-m", "uvicorn", "services.kap_worker.main:app", "--host", "0.0.0.0", "--port", "8002"]
