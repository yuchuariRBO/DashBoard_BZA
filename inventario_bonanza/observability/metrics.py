"""Bounded labels only: resolver name, HTTP method/status, database alias/operation."""

from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter(
    "bonanza_http_requests_total", "Respuestas HTTP", ["route", "method", "status"]
)
LATENCY = Histogram(
    "bonanza_http_duration_seconds",
    "Tiempo hasta cabeceras de respuesta",
    ["route", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
INFLIGHT = Gauge(
    "bonanza_http_inflight", "Peticiones en curso", multiprocess_mode="livesum"
)
TIMEOUTS = Counter(
    "bonanza_http_slow_requests_total", "Peticiones que superan el umbral configurado"
)
QUERIES = Histogram(
    "bonanza_db_query_duration_seconds",
    "Duración observada de ejecución SQL",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 5),
)
DB_ERRORS = Counter("bonanza_db_errors_total", "Errores al ejecutar SQL")
SLOW_SQL = Counter("bonanza_db_slow_queries_total", "SQL sobre el umbral configurado")
AUTH_FAILURES = Counter("bonanza_auth_failures_total", "Autenticaciones rechazadas")
MODULES = Counter("bonanza_module_requests_total", "Actividad agregada", ["module"])
ACTIVITY_FAILURES = Counter(
    "bonanza_activity_write_errors_total", "Muestreos de actividad no persistidos"
)


def registry():
    import os

    from prometheus_client import REGISTRY, CollectorRegistry, multiprocess

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        value = CollectorRegistry()
        multiprocess.MultiProcessCollector(value)
        return value
    return REGISTRY


WORKERS = Gauge(
    "bonanza_workers_alive",
    "Trabajadores instrumentados vivos (requiere child_exit en multiproceso)",
    multiprocess_mode="livesum",
)
WORKERS.set(1)
