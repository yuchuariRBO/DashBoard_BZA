"""Hermetic tests: never load .env, production SQLite, MinIO or external mail."""

import os
import tempfile
from pathlib import Path

_test_root = Path(tempfile.gettempdir()) / f"bonanza-tests-{os.getuid()}"
os.environ["BONANZA_LOAD_ENV_FILE"] = "False"
os.environ["LOG_DIR"] = str(_test_root / "logs")
os.environ["RUN_DIR"] = str(_test_root / "run")
from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SUPPORT_PRIVATE_ROOT = _test_root / "private"
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "monitoring": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "bonanza-monitor-tests",
    },
}
PROMETHEUS_URL = ""
GRAFANA_URL = ""
MONITOR_SERVICE_PROBES = {}
# Ignore credentials inherited from a deployment shell as well as from .env.
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_IDS = []
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
PLATE_LOOKUP_API_TOKEN = ""
PERSON_LOOKUP_API_TOKEN = ""
FACE_GALLERY_API_TOKEN = ""
MINIO_ACCESS_KEY = ""
MINIO_SECRET_KEY = ""
AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""
MONITOR_METRICS_TOKEN = ""
