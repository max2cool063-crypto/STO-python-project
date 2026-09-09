# Локальная проверка feature/production-hardening

Дата: 2026-09-08. Commit: `d8935c2`.

## Область проверки

Изучены README, настройки Django, Docker/CI, изменения относительно main,
регистрация, ограничения входа, напоминания и backup/restore-скрипты.
Это проверка запуска и тестов с выборочным анализом кода, не полный аудит безопасности.
Исходники приложения и тестов не изменялись.

## Подготовленное окружение

- Python 3.11.16, Django 5.2.17, PostgreSQL 15.19, Redis 7.4.11.
- Все 11 прямых зависимостей совпадают с requirements.txt; `pip check` успешен.
- Использован существующий образ `sto_booking-web:latest`, ID
  `sha256:6fb91d35ae4063e3351df1818cded2eeaaba1c5cf2ac043a5de190f64252195a`.
  Текущая рабочая копия смонтирована в `/app`, поэтому проверялся код указанного commit,
  а не сохранённый в образе код.
- Чистая сборка Dockerfile была прервана из-за медленной загрузки пакетов
  (Django 8.3 MB скачивался 4:26); успешная чистая сборка не подтверждена.
- `.env.local` содержит случайные локальные секреты и console email backend;
  файл исключён из Git. Внешние письма не отправляются.
- Изолированные сервисы: `sto-hardening-local-db-1`, `sto-hardening-local-redis-1`.
  Используется отдельный volume `sto-hardening-local_postgres_data`.
- Приложение: контейнер `sto-hardening-web`, http://localhost:8001.
  Порт 8000 уже занят другим существующим приложением.
- Тесты: контейнер `sto-hardening-tests`, отдельная БД `test_sto`, Redis DB 2.
  Приложение использует БД `sto`, Redis DB 1.

## Проверки

- Docker Compose config: успешно.
- `python -m pip check`: успешно.
- `python manage.py check`: 0 проблем.
- `python manage.py check --deploy --fail-level WARNING`: 0 проблем с HTTPS-профилем CI.
  Это отдельная проверка настроек, локальный сайт работает по HTTP.
- `python manage.py makemigrations --check --dry-run`: No changes detected.
- `python manage.py migrate --noinput`: все миграции применились на новой PostgreSQL.
- `python manage.py collectstatic --noinput`: 245 файлов, 715 операций post-processing;
  `staticfiles/staticfiles.json` создан.
- HTTP: `/healthz/` возвращает 200 и `ok`, `/` возвращает 200.
- Полный набор `python manage.py test booking.tests --verbosity 2`: **273 теста, OK**,
  799.547 секунды (13 минут 20 секунд), код завершения 0. Тестовая БД удалена раннером.
  Полный журнал: [local-tests-2026-09-08.log](local-tests-2026-09-08.log)
  (локальный файл, исключён из Git по маске `*.log`).
- Полный разрушительный backup/restore smoke test и контейнерный HTTPS health smoke test
  из CI не выполнялись.

## Найденные проблемы

### 1. Регистрация возвращает HTTP 500 для длинного допустимого email

`booking/views/auth.py:98`: email используется как Django username без проверки
его максимальной длины. У username предел 150 символов, email validator допускает
более длинные адреса. Обработчик ловит IntegrityError, но здесь возникает DataError.

На локальной PostgreSQL воспроизведено с адресом:

```python
email = 'a' * 64 + '@' + 'b' * 60 + '.' + 'c' * 30 + '.com'
```

`validate_email(email)` проходит; длина 160. POST `/accounts/register/` возвращает
500. Точная ошибка: `django.db.utils.DataError: value too long for type character varying(150)`.
Нужна проверка ограничения username до записи либо отдельная схема формирования username,
а также регрессионный тест.

### 2. Shell-скрипты не запускаются из Windows checkout с CRLF

`git ls-files --eol scripts` показывает `i/lf w/crlf`; `core.autocrlf=true`.
В репозитории отсутствует `.gitattributes`, закрепляющий LF для `.sh`.
`bash -n` отклоняет все три файла: backup.sh:19, restore.sh:19,
ci_backup_restore_smoke.sh:10. После преобразования временных копий в LF
все три проходят синтаксическую проверку. Исходные файлы не менялись.
Нужно закрепить `*.sh text eol=lf` и нормализовать checkout.
Это проблема воспроизводимости на Windows; в Git сами файлы хранятся с LF.

### 3. Предупреждения collectstatic

Дублируются `admin/js/cancel.js` и `admin/js/popup_response.js`;
выбирается первый найденный файл. Сборка статики успешна.
Это предупреждение о коллизиях Django/Jazzmin, а не подтверждённый сбой UI.

## Повторный запуск подготовленного окружения

Из корня проекта, в PowerShell:

```powershell
docker compose --env-file .env.local -p sto-hardening-local up -d db redis
docker start sto-hardening-web
```

После завершения текущего прогона повторить проверки и тесты можно так:

```powershell
docker start -a sto-hardening-tests
```

Посмотреть логи приложения:

```powershell
docker logs --tail 100 sto-hardening-web
```

Остановить только созданное окружение, сохранив данные:

```powershell
docker stop sto-hardening-web
docker compose --env-file .env.local -p sto-hardening-local stop db redis
```

Это команды для уже созданных контейнеров. Обычный `docker compose up` без
`--env-file .env.local -p sto-hardening-local` не выбирает данное окружение.
Если контейнеры удалить, потребуется повторить их создание.
