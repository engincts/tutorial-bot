FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Dummy app paketi — bağımlılıkları önce kur, kaynak değişince cache bozulmasın
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir --timeout=300 --retries=5 ".[dev]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005", "--reload"]
