FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY services/market_data_worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared_db/ /app/shared_db/
COPY services/market_data_worker/ /app/services/market_data_worker/

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["python", "services/market_data_worker/main.py"]
