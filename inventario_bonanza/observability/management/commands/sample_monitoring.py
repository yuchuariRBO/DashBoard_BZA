"""Run out of band every minute; deliberately has no notification transport."""

import time

import requests
from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand

from observability.alerts import evaluate
from observability.prometheus import performance, valid_base
from observability.snapshot import snapshot

cache = caches["monitoring"]


class Command(BaseCommand):
    help = (
        "Muestrea servicios autorizados y evalúa alertas locales (sin envíos externos)."
    )

    def handle(self, *args, **options):
        data = snapshot(force=True)
        perf = performance()
        services = []
        # Only configured URLs, never a ticket, request parameter or database-supplied URL.
        for name, url in settings.MONITOR_SERVICE_PROBES.items():
            if name not in ("minio", "people_api", "plates_api") or not valid_base(url):
                continue
            started = time.perf_counter()
            try:
                response = requests.get(url, timeout=2, allow_redirects=False)
                up = 200 <= response.status_code < 300
            except requests.RequestException:
                up = False
            services.append(
                {"name": name, "up": up, "duration": time.perf_counter() - started}
            )
        # Shared file cache in the example deployment; default locmem is single-process only.
        cache.set("bonanza_service_health", services, 180)
        values = perf["values"]
        signals = {
            "service_down": sum(not s["up"] for s in services) if services else None,
            "errors_5xx": values.get("errors_5xx"),
            "latency_p95": values.get("p95"),
            "db_slow": values.get("db_slow"),
            "db_errors": values.get("db_errors"),
            "cpu": data["infrastructure"].get("cpu_percent", values.get("cpu")),
            "memory": data["infrastructure"].get("memory_percent"),
            "disk": data["infrastructure"].get("disk_percent"),
            "tasks_failed": data["tasks_failed_recent"],
            "critical_tickets": sum(
                row["total"]
                for row in data["tickets"]
                if row["priority"] == "critical"
                and row["status"] not in ("resolved", "closed")
            ),
        }
        evaluate(
            signals,
            service_values={item["name"]: int(not item["up"]) for item in services},
        )
        self.stdout.write(
            "Muestreo y evaluación completados; no se enviaron notificaciones externas."
        )
