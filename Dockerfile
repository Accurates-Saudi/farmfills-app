FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        postgresql-client \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic needs the env vars to import settings; dummies are fine here
RUN SECRET_KEY=build-only \
    DATABASE_NAME=x DATABASE_USER=x DATABASE_PASS=x DATABASE_HOST=x DATABASE_PORT=5432 \
    python manage.py collectstatic --noinput

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "farmfills.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
