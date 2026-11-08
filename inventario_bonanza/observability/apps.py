from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    name = "observability"
    verbose_name = "Centro de monitoreo"

    def ready(self):
        from . import signals  # noqa: F401
