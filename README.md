# STO-python-project

Django-приложение для онлайн-записи на технический осмотр автомобилей.

## Стек

- Django 5.2.17 LTS
- Python 3.11
- PostgreSQL 15
- Gunicorn
- WhiteNoise
- Jazzmin 3.0.2
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

При запуске Compose сначала ждёт готовности PostgreSQL, затем одноразовый сервис `migrate` выполняет `python manage.py migrate --noinput`. Только после его успешного завершения запускается `web`. Это исключает выполнение миграций каждым web-процессом при рестарте или масштабировании.

Статические файлы собираются командой `collectstatic` во время `docker build` и уже находятся внутри production-образа. Web-контейнер не пересобирает static при старте.

Приложение доступно на `http://localhost:8000`.

В production не используйте bind mount исходного кода: compose хранит только пользовательские media-файлы в отдельном volume.

При запуске образа вне Compose миграции нужно выполнить отдельным release/deploy шагом до старта web-процессов, например:

```bash
python manage.py migrate --noinput
```

## Production HTTPS и security settings

Для локального HTTP используйте `.env.example`. Для production используйте `.env.production.example` как шаблон и храните реальные значения только в secret store или локальном `.env.production`, который исключён из Git.

Минимально для публичного HTTPS deployment должны быть заданы `DEBUG=False`, корректные `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`, а также включены `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` и HSTS.

Если TLS завершается на reverse proxy, включайте `SECURE_PROXY_SSL_HEADER=True` только когда этот proxy находится под вашим контролем и всегда корректно выставляет `X-Forwarded-Proto`. Иначе возможны ошибки определения HTTPS или redirect loop.

`SECURE_HSTS_INCLUDE_SUBDOMAINS` включайте только если все поддомены обслуживаются по HTTPS. `SECURE_HSTS_PRELOAD` не включайте автоматически: это отдельное осознанное решение после проверки требований HSTS preload.

Перед production deployment полезно выполнить:

```bash
python manage.py check --deploy
```

CI также выполняет строгий `check --deploy --fail-level WARNING` на безопасном production-профиле настроек, чтобы новые изменения не отключили обязательные Django security-механизмы.

## Проверка Django

В контейнере web:

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test booking.tests --verbosity 2
```

## CI

GitHub Actions выполняет `check`, строгую production security-проверку, проверку миграций и весь набор `booking.tests` на Python 3.11 и PostgreSQL 15 — тех же основных версиях, что используются production-контейнерами. Отдельный container job валидирует Docker Compose, собирает production-образ и проверяет, что `collectstatic` уже выполнен внутри образа.

## Переменные окружения

Все секреты и production-настройки задаются через environment variables. Не коммитьте реальные `.env`, `.env.production` или `.env.local`.

## Структура

- `booking/models.py` — модели и правила бронирования.
- `booking/views/` — клиентский и станционный кабинеты.
- `booking/static/booking/` — CSS, JS и изображения.
- `templates/` — HTML-шаблоны.
- `booking/tests/` — регрессионные и security-тесты.
