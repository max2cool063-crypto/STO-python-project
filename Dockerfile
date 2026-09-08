# Dockerfile - STO Booking (Django 5.2 LTS + Gunicorn)

# Stage 1: build deps
FROM python:3.11-slim AS deps

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2: runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libjpeg62-turbo postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY . .

RUN mkdir -p /app/staticfiles /app/media \
    && useradd --create-home --shell /bin/false --uid 1000 appuser \
    && chown -R appuser:appuser /app /home/appuser

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=auto_booking.settings \
    HOME=/home/appuser

# Static assets are immutable application artifacts. Build them once into the
# image rather than regenerating them every time a web replica starts.
RUN SECRET_KEY=container-build-only \
    POSTGRES_DB=container_build \
    POSTGRES_USER=container_build \
    POSTGRES_PASSWORD=container_build \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Database migrations are intentionally NOT run here. Docker Compose executes
# them in a dedicated one-shot migrate service before web is allowed to start.
CMD ["sh", "-c", "\
  until pg_isready -h ${POSTGRES_HOST:-db} -p ${POSTGRES_PORT:-5432}; do echo 'Waiting for DB...'; sleep 2; done && \
  gunicorn auto_booking.wsgi:application --config gunicorn.conf.py"]
