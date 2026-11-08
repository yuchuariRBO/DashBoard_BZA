"""Development-only WSGI wrapper for local static assets, never private uploads."""

import os
from django.core.wsgi import get_wsgi_application
from django.contrib.staticfiles.handlers import StaticFilesHandler

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "inventario_bonanza.settings_observability_dev"
)
application = StaticFilesHandler(get_wsgi_application())
