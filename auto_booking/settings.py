from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# FIX: SECRET_KEY только из переменной окружения
SECRET_KEY = os.environ["SECRET_KEY"]

# FIX: DEBUG=False по умолчанию — безопасный дефолт
DEBUG = os.getenv("DEBUG", "False") == "True"

# FIX: ALLOWED_HOSTS из переменной окружения вместо ["*"]
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_L10N = False  # Отключаем локализацию чисел — иначе float рендерится с запятой в ru локали
USE_TZ = True

YANDEX_MAPS_API_KEY = os.getenv("YANDEX_MAPS_API_KEY", "")

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "booking",
]

JAZZMIN_SETTINGS = {
    "site_title": "СТО Бронирование",
    "site_header": "Администрирование СТО",
    "site_brand": "СТО Booking",
    "welcome_sign": "Добро пожаловать в систему",
    "language_chooser": False,
    "icons": {
        "booking.station": "fas fa-warehouse",
        "booking.appointment": "fas fa-calendar-check",
    },
    "show_sidebar": True,
    "navigation_expanded": True,
    "custom_links": {
        "booking": [{
            "name": "Импорт из РСА",
            "url": "/admin/booking/station/import-rsa/",
            "icon": "fas fa-file-import",
            "permissions": ["booking.view_station"],
        }]
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # FIX: добавлен XFrameOptionsMiddleware против кликджекинга
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "auto_booking.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "booking.context_processors.yandex_key",
            ],
        },
    }
]

WSGI_APPLICATION = "auto_booking.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": int(os.getenv("POSTGRES_PORT", 5432)),
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "/accounts/post-login/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

# FIX: все email-настройки только из переменных окружения
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
DEFAULT_CHARSET = "utf-8"
EMAIL_TIMEOUT = 20

# FIX: CSRF_TRUSTED_ORIGINS из env для гибкости в продакшене
_trusted = os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:8000")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _trusted.split(",") if o.strip()]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
