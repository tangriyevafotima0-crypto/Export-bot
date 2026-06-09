FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/logs /app/data/backups /app/data/exports /app/data/archive

VOLUME ["/app/data"]

EXPOSE 5000 8080

CMD ["python", "main.py"]
