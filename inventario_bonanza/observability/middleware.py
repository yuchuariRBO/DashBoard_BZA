import time
from collections import OrderedDict
from contextlib import ExitStack
from threading import Lock

from django.conf import settings
from django.db import DatabaseError, connections
from django.urls import Resolver404, resolve
from django.utils import timezone

from .metrics import (
    ACTIVITY_FAILURES,
    DB_ERRORS,
    INFLIGHT,
    LATENCY,
    MODULES,
    QUERIES,
    REQUESTS,
    SLOW_SQL,
    TIMEOUTS,
)

_seen = OrderedDict()
_seen_lock = Lock()


def record_activity(user):
    """At most one indexed upsert per user/minute/worker, bounded local cache."""
    if not user.is_authenticated:
        return
    current = time.monotonic()
    with _seen_lock:
        if (
            current - _seen.get(user.pk, float("-inf"))
            < settings.MONITOR_ACTIVITY_SAMPLE_SECONDS
        ):
            return
        _seen[user.pk] = current
        _seen.move_to_end(user.pk)
        if len(_seen) > 4096:
            _seen.popitem(last=False)
    from .models import UserActivity

    try:
        UserActivity.objects.update_or_create(
            user_id=user.pk, defaults={"last_seen": timezone.now()}
        )
    except DatabaseError:
        ACTIVITY_FAILURES.inc()


def measure_sql(execute, sql, params, many, context):
    start = time.perf_counter()
    operation = str(sql).lstrip().split(None, 1)[0].lower() if sql else "other"
    if operation not in (
        "select",
        "insert",
        "update",
        "delete",
        "begin",
        "savepoint",
        "release",
        "pragma",
    ):
        operation = "other"
    try:
        return execute(sql, params, many, context)
    except DatabaseError:
        DB_ERRORS.inc()
        raise
    finally:
        duration = time.perf_counter() - start
        QUERIES.labels(operation).observe(duration)
        if duration > settings.MONITOR_SLOW_SQL_SECONDS:
            SLOW_SQL.inc()


class MetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.OBSERVABILITY_ENABLED:
            return self.get_response(request)
        try:
            match = resolve(request.path_info)
            route = match.view_name or "unnamed"
        except Resolver404:
            route = "unmatched"
        if route == "observability:metrics":
            return self.get_response(request)
        method = (
            request.method
            if request.method
            in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
            else "OTHER"
        )
        module = (
            "support"
            if route.startswith("support:")
            else "monitoring"
            if route.startswith("observability:")
            else "platform"
        )
        start = time.perf_counter()
        status = 500
        INFLIGHT.inc()
        try:
            with ExitStack() as stack:
                for connection in connections.all():
                    stack.enter_context(connection.execute_wrapper(measure_sql))
                response = self.get_response(request)
            status = response.status_code
            user = getattr(request, "user", None)
            if user and status < 500:
                record_activity(user)
            return response
        finally:
            elapsed = time.perf_counter() - start
            INFLIGHT.dec()
            REQUESTS.labels(route, method, str(status)).inc()
            LATENCY.labels(route, method).observe(elapsed)
            MODULES.labels(module).inc()
            if elapsed > settings.MONITOR_SLOW_REQUEST_SECONDS:
                TIMEOUTS.inc()
