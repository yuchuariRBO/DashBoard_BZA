import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent


def load_env_file(path):
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


if os.environ.get('BONANZA_LOAD_ENV_FILE', 'True') == 'True':
    load_env_file(PROJECT_DIR / '.env')

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'change-me',
)
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', '35.252.253.187,localhost,127.0.0.1,bonanza.robio-ai.com')
CSRF_TRUSTED_ORIGINS = env_list(
    'CSRF_TRUSTED_ORIGINS',
    'https://35.252.253.187,https://localhost,https://127.0.0.1,https://bonanza.robio-ai.com',
)

SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 86400 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_IDS = [
    chat_id.strip()
    for chat_id in os.environ.get('TELEGRAM_CHAT_IDS', '').split(',')
    if chat_id.strip()
]
PLATE_LOOKUP_API_TOKEN = os.environ.get('PLATE_LOOKUP_API_TOKEN', '')
PERSON_LOOKUP_API_TOKEN = os.environ.get('PERSON_LOOKUP_API_TOKEN', '')
FACE_GALLERY_API_TOKEN = os.environ.get('FACE_GALLERY_API_TOKEN', '')

AUTH_USER_MODEL = 'gestion_personal.CustomUser'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'role_based_redirect'
LOGOUT_REDIRECT_URL = 'login'

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "gestion_personal",  # Nuestra aplicación
    "support",
    "observability",
    "crispy_forms",
    "crispy_bootstrap5",
    "storages",
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    "observability.middleware.MetricsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "inventario_bonanza.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "support.context_processors.module_access",
            ],
        },
    },
]

WSGI_APPLICATION = "inventario_bonanza.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DATABASE_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get("DATABASE_NAME", str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
USE_TZ = True

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

MINIO_ENDPOINT_URL = os.environ.get('MINIO_ENDPOINT_URL', 'http://127.0.0.1:9000')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', '')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', '')
MINIO_BUCKET_NAME = os.environ.get('MINIO_BUCKET_NAME', 'dashboard-personal')

AWS_ACCESS_KEY_ID = MINIO_ACCESS_KEY
AWS_SECRET_ACCESS_KEY = MINIO_SECRET_KEY
AWS_STORAGE_BUCKET_NAME = MINIO_BUCKET_NAME
AWS_S3_ENDPOINT_URL = MINIO_ENDPOINT_URL
AWS_S3_REGION_NAME = os.environ.get('MINIO_REGION_NAME', 'us-east-1')
AWS_S3_ADDRESSING_STYLE = 'path'
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False

STORAGES = {
    'default': {
        'BACKEND': 'gestion_personal.storage_backends.MinioMediaStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

UPLOAD_DIRS = {
    'personas': MEDIA_ROOT / 'fotos_personal',
    'sanciones': MEDIA_ROOT / 'sanciones',
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Generated files are kept outside the application source tree.
LOG_DIR = Path(os.environ.get('LOG_DIR', str(PROJECT_DIR / 'logs')))
RUN_DIR = Path(os.environ.get('RUN_DIR', str(PROJECT_DIR / 'run')))
RUN_DIR.mkdir(parents=True, exist_ok=True)
for directory in ('lookups/people', 'lookups/plates', 'gunicorn'):
    (LOG_DIR / directory).mkdir(parents=True, exist_ok=True)

from .logging_config import build_logging_config
LOGGING = build_logging_config(LOG_DIR)

# Public error pages must never include diagnostic details.
CSRF_FAILURE_VIEW = 'gestion_personal.error_views.csrf_failure'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True

# Support files are intentionally outside MEDIA_ROOT and the public MinIO proxy.
SUPPORT_PRIVATE_ROOT = Path(os.environ.get('SUPPORT_PRIVATE_ROOT', str(PROJECT_DIR / 'private_support')))
SUPPORT_MAX_UPLOAD_BYTES = int(os.environ.get('SUPPORT_MAX_UPLOAD_BYTES', str(5 * 1024 * 1024)))
OBSERVABILITY_ENABLED = os.environ.get('OBSERVABILITY_ENABLED', 'True') == 'True'
MONITOR_ACTIVE_WINDOW_SECONDS = int(os.environ.get('MONITOR_ACTIVE_WINDOW_SECONDS', '900'))
MONITOR_ACTIVITY_SAMPLE_SECONDS = int(os.environ.get('MONITOR_ACTIVITY_SAMPLE_SECONDS', '60'))
MONITOR_SNAPSHOT_SECONDS = int(os.environ.get('MONITOR_SNAPSHOT_SECONDS', '30'))
MONITOR_SLOW_REQUEST_SECONDS = float(os.environ.get('MONITOR_SLOW_REQUEST_SECONDS', '10'))
MONITOR_SLOW_SQL_SECONDS = float(os.environ.get('MONITOR_SLOW_SQL_SECONDS', '0.5'))
MONITOR_METRICS_TOKEN = os.environ.get('MONITOR_METRICS_TOKEN', '')
PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', '')
GRAFANA_URL = os.environ.get('GRAFANA_URL', '')
# Explicit allowlist, never derived from request input. Empty disables probes.
MONITOR_SERVICE_PROBES = json.loads(os.environ.get('MONITOR_SERVICE_PROBES', '{}'))

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
          'monitoring': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                         'LOCATION': str(RUN_DIR / 'monitoring-cache'), 'TIMEOUT': 180}}
