import multiprocessing

# Адрес и порт
bind = "0.0.0.0:8000"

# Количество воркеров: 2 × CPU + 1 (стандартная формула для sync-воркеров)
workers = multiprocessing.cpu_count() * 2 + 1

# Тип воркера — sync подходит для Django
worker_class = "sync"

# Таймаут на обработку запроса (сек)
timeout = 60

# Keep-alive соединения (сек)
keepalive = 5

# Перезапуск воркера после N запросов — защита от утечек памяти
max_requests = 1000
max_requests_jitter = 100

# Логи в stdout/stderr — правильно для Docker
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Время на завершение текущих запросов при перезапуске
graceful_timeout = 30

# Форвардинг заголовков (если за nginx/proxy)
forwarded_allow_ips = "*"
