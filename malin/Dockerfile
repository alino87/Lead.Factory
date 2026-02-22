FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY malin/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY malin/ ./malin/

RUN chmod +x ./malin/start.sh

EXPOSE 8000

CMD ["./malin/start.sh"]
