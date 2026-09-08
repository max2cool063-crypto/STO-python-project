# STO-python-project

Django-приложение для онлайн-записи на технический осмотр автомобилей.

## Стек

- Django 5.2.17 LTS
- Python 3.11
- PostgreSQL 15
- Gunicorn
- WhiteNoise
- Jazzmin 3.0.5
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

Статические файлы собираются командой `collectstatic` во время `docker build` через `whitenoise.storage.CompressedManifestStaticFilesStorage` и уже находятся внутри production-образа. Web-контейнер не пересобирает static при старте.

Приложение доступно на `http://localhost:8000`.

В production не используйте bind mount исходного кода: compose хранит только пользовательские media-файлы в отдельном volume.

При запуске образа вне Compose миграции нужно выполнить отдельным release/deploy шагом до старта web-процессов, например:

```bash
python manage.py migrate --noinput
```

## Production HTTPS и security settings

Для локального HTTP используйте `.env.example`. Для production используйте `.env.production.example` как шаблон и храните реальные значения только в secret store или локальном `.env.production`, который исключён из Git.

Предоставленный `docker-compose.yml` по умолчанию читает `.env`. Чтобы использовать отдельный production-файл без переименования, задайте `ENV_FILE` для всех команд Compose:

```bash
ENV_FILE=.env.production docker compose build
ENV_FILE=.env.production docker compose up -d
```

Тот же `ENV_FILE=.env.production` нужно передавать командам backup/restore, чтобы они работали с тем же deployment-конфигом.

Минимально для публичного HTTPS deployment должны быть заданы `DEBUG=False`, корректные `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`, а также включены `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` и HSTS.

Если TLS завершается на reverse proxy, включайте `SECURE_PROXY_SSL_HEADER=True` только когда этот proxy находится под вашим контролем и всегда корректно выставляет `X-Forwarded-Proto`. Иначе возможны ошибки определения HTTPS или redirect loop.

`SECURE_HSTS_INCLUDE_SUBDOMAINS` включайте только если все поддомены обслуживаются по HTTPS. `SECURE_HSTS_PRELOAD` не включайте автоматически: это отдельное осознанное решение после проверки требований HSTS preload.

Перед production deployment полезно выполнить:

```bash
python manage.py check --deploy
```

CI также выполняет строгий `check --deploy --fail-level WARNING` на безопасном production-профиле настроек, чтобы новые изменения не отключили обязательные Django security-механизмы.

## Backup и restore

Production-данные состоят как минимум из PostgreSQL и пользовательских файлов в `media_data`. Оба компонента должны резервироваться вместе.

Создать backup:

```bash
bash scripts/backup.sh
```

При deployment с отдельным production env-файлом:

```bash
ENV_FILE=.env.production bash scripts/backup.sh
```

По умолчанию создаётся каталог `./backups/<UTC timestamp>/` с `postgres.dump`, `media.tar.gz`, `manifest.txt` и SHA-256 checksums. Каталог `backups/` исключён из Git и Docker build context, но это не является системой хранения резервных копий: после создания переносите backup в зашифрованное off-host хранилище.

Для максимально согласованной копии БД и media можно кратковременно остановить работающие `web`/`cron` на время backup:

```bash
BACKUP_QUIESCE_APP=True bash scripts/backup.sh
```

Скрипт запоминает состояние `web` и `cron` до остановки и после backup возобновляет только те сервисы, которые действительно работали. Обычный `pg_dump` сам по себе создаёт транзакционно согласованную копию БД, но без остановки приложения DB dump и media archive снимаются не в один момент времени.

Восстановление является **разрушающей операцией**: текущая БД пересоздаётся, а содержимое media volume заменяется содержимым backup. Запускайте restore только из проверенной копии и только в запланированное окно обслуживания:

```bash
RESTORE_CONFIRM=YES bash scripts/restore.sh backups/20260908T120000Z
```

При отдельном production env-файле:

```bash
ENV_FILE=.env.production RESTORE_CONFIRM=YES bash scripts/restore.sh backups/20260908T120000Z
```

Перед восстановлением скрипт проверяет SHA-256 checksums, если они есть, останавливает `web`/`cron`, пересоздаёт PostgreSQL, восстанавливает media, один раз применяет миграции текущего кода и только затем снова запускает приложение. Если restore прервётся ошибкой, не открывайте приложение для пользователей до выяснения причины и повторной проверки данных.

После каждого restore вручную проверьте вход, несколько последних записей, историю статусов и защищённые фотографии. В production backup считается надёжным только после периодической тестовой процедуры восстановления на отдельном окружении. Реальный `.env`/секреты в backup-архив не включаются и должны резервироваться отдельно в защищённом secret store.

## Проверка Django

В контейнере web:

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test booking.tests --verbosity 2
```

## CI

GitHub Actions выполняет `check`, строгую production security-проверку, проверку миграций, `collectstatic` с manifest-backed WhiteNoise storage и весь набор `booking.tests` на Python 3.11 и PostgreSQL 15 — тех же основных версиях, что используются production-контейнерами. Отдельный container job валидирует Docker Compose, проверяет синтаксис backup/restore scripts, собирает production-образ и проверяет наличие обычного static-файла и `staticfiles.json` внутри образа.

## Переменные окружения

Все секреты и production-настройки задаются через environment variables. Не коммитьте реальные `.env`, `.env.production` или `.env.local`.

## Структура

- `booking/models.py` — модели и правила бронирования.
- `booking/views/` — клиентский и станционный кабинеты.
- `booking/static/booking/` — CSS, JS и изображения.
- `templates/` — HTML-шаблоны.
- `booking/tests/` — регрессионные и security-тесты.
- `scripts/backup.sh` и `scripts/restore.sh` — backup/restore PostgreSQL и media.
