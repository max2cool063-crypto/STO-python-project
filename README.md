# STO-python-project

Django-приложение для онлайн-записи на технический осмотр автомобилей.

## Стек

- Django 5.1
- PostgreSQL 15
- Gunicorn
- WhiteNoise
- Jazzmin
- Pillow
- Docker Compose

## Запуск через Docker

1. Скопируйте `.env.example` в `.env` и заполните секреты.
2. Соберите контейнеры:

```bash
docker compose build
```

3. Запустите приложение:

```bash
docker compose up
```

Приложение доступно на `http://localhost:8000`.

В production не используйте bind mount исходного кода: compose хранит только пользовательские media-файлы в отдельном volume.

## Проверка Django

В контейнере web:

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test booking.tests --verbosity 2
```

## CI

GitHub Actions выполняет `check`, проверку миграций и весь набор `booking.tests`.

## Переменные окружения

Все секреты и production-настройки задаются через `.env`. Для HTTPS в production настройте `SECURE_SSL_REDIRECT`, secure cookies и HSTS согласно `.env.example`.

## Структура

- `booking/models.py` — модели и правила бронирования.
- `booking/views/` — клиентский и станционный кабинеты.
- `booking/static/booking/` — CSS, JS и изображения.
- `templates/` — HTML-шаблоны.
- `booking/tests/` — регрессионные и security-тесты.
