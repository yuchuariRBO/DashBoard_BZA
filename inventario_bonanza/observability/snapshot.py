"""Cheap snapshots; no per-request network probe, process scan or directory walk."""

import shutil
import time
from datetime import timedelta
from pathlib import Path
from threading import Lock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import connection
from django.db.models import Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from gestion_personal.models import PersonLookupRecord, PlateLookupRecord
from support.models import Status, Ticket

from .models import UserActivity

_lock = Lock()
_cached = None
_cached_at = 0
_cpu = None


def infrastructure():
    global _cpu
    result = {}
    try:
        values = [
            int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        ]
        sample = (sum(values[:8]), values[3] + values[4])
        if _cpu and sample[0] > _cpu[0]:
            result["cpu_percent"] = max(
                0, min(100, 100 * (1 - (sample[1] - _cpu[1]) / (sample[0] - _cpu[0])))
            )
        _cpu = sample
        mem = {
            line.split(":")[0]: int(line.split()[1]) * 1024
            for line in Path("/proc/meminfo").read_text().splitlines()
        }
        result["memory_percent"] = 100 * (1 - mem["MemAvailable"] / mem["MemTotal"])
        result["uptime_seconds"] = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, KeyError, IndexError):
        pass
    usage = shutil.disk_usage(settings.BASE_DIR)
    result["disk_percent"] = 100 * usage.used / usage.total
    return result


def snapshot(force=False):
    global _cached, _cached_at
    with _lock:
        if (
            not force
            and _cached is not None
            and time.monotonic() - _cached_at < settings.MONITOR_SNAPSHOT_SECONDS
        ):
            return _cached
        now = timezone.now()
        users = get_user_model().objects.aggregate(
            registered=Count("pk"), enabled=Count("pk", filter=Q(is_active=True))
        )
        users["active"] = UserActivity.objects.filter(
            last_seen__gte=now
            - timedelta(seconds=settings.MONITOR_ACTIVE_WINDOW_SECONDS),
            user__is_active=True,
        ).count()
        users["sessions"] = (
            Session.objects.filter(expire_date__gt=now).count()
            if settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
            else None
        )
        tickets = list(
            Ticket.objects.values("status", "priority").annotate(total=Count("pk"))
        )
        response = ExpressionWrapper(
            F("first_response_at") - F("created_at"), output_field=DurationField()
        )
        resolution = ExpressionWrapper(
            F("resolved_at") - F("created_at"), output_field=DurationField()
        )
        timing = Ticket.objects.aggregate(
            response_sum=Sum(response),
            response_count=Count("first_response_at"),
            resolution_sum=Sum(resolution),
            resolution_count=Count("resolved_at"),
            sla_count=Count(
                "pk",
                filter=Q(resolved_at__isnull=False, resolution_due_at__isnull=False),
            ),
            sla_met=Count("pk", filter=Q(resolved_at__lte=F("resolution_due_at"))),
        )
        for key in ("response_sum", "resolution_sum"):
            timing[key] = timing[key].total_seconds() if timing[key] else 0
        queues = {}
        for name, model in [
            ("people", PersonLookupRecord),
            ("plates", PlateLookupRecord),
        ]:
            queues[name] = list(
                model.objects.values("lookup_status").annotate(total=Count("pk"))
            )
        tasks_failed_recent = sum(
            model.objects.filter(
                lookup_status="failed", updated_at__gte=now - timedelta(minutes=15)
            ).count()
            for model in (PersonLookupRecord, PlateLookupRecord)
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        _cached = {
            "generated_at": now,
            "users": users,
            "tickets": tickets,
            "timing": timing,
            "queues": queues,
            "tasks_failed_recent": tasks_failed_recent,
            "infrastructure": infrastructure(),
            "database_vendor": connection.vendor,
            "database_ok": True,
        }
        _cached_at = time.monotonic()
        return _cached


def prometheus_snapshot():
    from prometheus_client import CollectorRegistry, generate_latest
    from prometheus_client.core import GaugeMetricFamily
    from support.models import Priority

    data = snapshot()

    class Collector:
        def collect(self):
            def scalar(name, doc, value):
                if value is not None:
                    metric = GaugeMetricFamily(name, doc)
                    metric.add_metric([], value)
                    return metric

            for name, value in data["users"].items():
                metric = scalar(
                    "bonanza_users_" + name,
                    "Usuarios y sesiones almacenadas; active usa ventana temporal",
                    value,
                )
                if metric:
                    yield metric
            metric = GaugeMetricFamily(
                "bonanza_support_tickets",
                "Tickets por estado y prioridad",
                labels=["status", "priority"],
            )
            totals = {
                (row["status"], row["priority"]): row["total"]
                for row in data["tickets"]
            }
            for status in Status.values:
                for priority in Priority.values:
                    metric.add_metric(
                        [status, priority], totals.get((status, priority), 0)
                    )
            yield metric
            yield scalar(
                "bonanza_lookup_recent_failures",
                "Consultas fallidas actualizadas en los últimos 15 minutos",
                data["tasks_failed_recent"],
            )
            for name, value in data["timing"].items():
                yield scalar(
                    "bonanza_support_" + name,
                    "Acumulado del estado actual de tickets",
                    value,
                )
            for name, value in data["infrastructure"].items():
                yield scalar(
                    "bonanza_host_" + name, "Muestra del host que ejecuta Django", value
                )
            metric = GaugeMetricFamily(
                "bonanza_lookup_tasks",
                "Registros por estado de consulta",
                labels=["service", "status"],
            )
            for service, rows in data["queues"].items():
                for row in rows:
                    metric.add_metric([service, row["lookup_status"]], row["total"])
            yield metric
            metric = GaugeMetricFamily(
                "bonanza_database_info", "Motor configurado", labels=["vendor"]
            )
            metric.add_metric([data["database_vendor"]], 1)
            yield metric
            yield scalar("bonanza_database_available", "SELECT 1 correcto", 1)

    registry = CollectorRegistry()
    registry.register(Collector())
    return generate_latest(registry)
