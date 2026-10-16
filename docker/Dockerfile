FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости (psycopg2 требует libpq, gcc не нужен при использовании -binary)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Сначала зависимости — так слой кэшируется отдельно от кода
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Потом код
COPY . .

EXPOSE 8080

# Дефолтная команда — API. Для воркера переопределим в docker-compose
CMD ["python", "-m", "inventory_api"]