"""Loopback development stack with its own SQLite and private filesystem storage."""

import os
import tempfile
from pathlib import Path

_dev_root = Path(
    os.environ.get(
        "BONANZA_DEV_ROOT",
        str(Path(tempfile.gettempdir()) / f"bonanza-dev-{os.getuid()}"),
    )
)
os.environ["BONANZA_LOAD_ENV_FILE"] = "False"
os.environ["DATABASE_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DATABASE_NAME"] = str(_dev_root / "db.sqlite3")
os.environ["LOG_DIR"] = str(_dev_root / "logs")
os.environ["RUN_DIR"] = str(_dev_root / "run")
from .settings import *  # noqa: E402,F403

# Keep DEBUG off: error responses never reveal credentials or private paths.
DEBUG = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:18000", "http://127.0.0.1:18000"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(_dev_root / "media")},
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
SUPPORT_PRIVATE_ROOT = _dev_root / "support-private"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:19090")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://127.0.0.1:13000")
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_IDS = []
# Production CDN resources remain external; local static files need explicit serving.
PLATE_LOOKUP_API_TOKEN = ""
PERSON_LOOKUP_API_TOKEN = ""
FACE_GALLERY_API_TOKEN = ""
