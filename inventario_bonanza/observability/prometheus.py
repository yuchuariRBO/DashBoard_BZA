"""Fixed PromQL queries; no user-submitted queries or credential-bearing links."""

from urllib.parse import urlsplit

import requests
from django.conf import settings

QUERIES = {
    "cpu": "avg(bonanza_host_cpu_percent)",
    "rps": "sum(rate(bonanza_http_requests_total[5m]))",
    "rpm": "sum(rate(bonanza_http_requests_total[5m])) * 60",
    "mean": "sum(rate(bonanza_http_duration_seconds_sum[5m])) / clamp_min(sum(rate(bonanza_http_duration_seconds_count[5m])), 0.000001)",
    "p50": "histogram_quantile(0.50, sum by (le) (rate(bonanza_http_duration_seconds_bucket[5m])))",
    "p95": "histogram_quantile(0.95, sum by (le) (rate(bonanza_http_duration_seconds_bucket[5m])))",
    "p99": "histogram_quantile(0.99, sum by (le) (rate(bonanza_http_duration_seconds_bucket[5m])))",
    "errors_4xx": 'sum(rate(bonanza_http_requests_total{status=~"4.."}[5m]))',
    "errors_5xx": 'sum(rate(bonanza_http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(bonanza_http_requests_total[5m])), 0.000001)',
    "workers": "sum(bonanza_workers_alive)",
    "saturation": "sum(bonanza_http_inflight) / clamp_min(sum(bonanza_workers_alive),1)",
    "concurrent": "sum(bonanza_http_inflight)",
    "auth_failures": "sum(increase(bonanza_auth_failures_total[15m]))",
    "slow_requests": "sum(increase(bonanza_http_slow_requests_total[15m]))",
    "db_errors": "sum(increase(bonanza_db_errors_total[5m]))",
    "db_slow": "sum(rate(bonanza_db_slow_queries_total[5m]))",
    "qps": "sum(rate(bonanza_db_query_duration_seconds_count[5m]))",
    "top_routes": "topk(10,sum by (route) (rate(bonanza_http_requests_total[5m])))",
    "slow_routes": "topk(10,histogram_quantile(0.95,sum by (route,le) (rate(bonanza_http_duration_seconds_bucket[5m]))))",
    "modules": "sum by (module) (rate(bonanza_module_requests_total[5m]))",
}


def valid_base(value):
    p = urlsplit(value)
    return bool(
        p.hostname
        and p.scheme in ("http", "https")
        and not p.username
        and not p.password
        and not p.query
        and not p.fragment
    )


def performance():
    """One batched instant query with bounded labels and one two-second timeout."""
    if not settings.PROMETHEUS_URL or not valid_base(settings.PROMETHEUS_URL):
        return {
            "available": False,
            "values": {},
            "routes": {},
            "reason": "Prometheus no configurado",
        }
    # Label each expression; one request avoids N independent timeout windows.
    expr = " or ".join(
        f'label_replace(({query}), "indicator", "{key}", "", "")'
        for key, query in QUERIES.items()
    )
    try:
        response = requests.get(
            settings.PROMETHEUS_URL.rstrip("/") + "/api/v1/query",
            params={"query": expr},
            timeout=2,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            raise ValueError()
        values = {}
        routes = {}
        import math

        for item in payload["data"]["result"]:
            key = item["metric"]["indicator"]
            value = float(item["value"][1])
            if not math.isfinite(value):
                continue
            if key in ("top_routes", "slow_routes", "modules"):
                routes.setdefault(key, []).append(
                    {
                        "name": item["metric"].get(
                            "route", item["metric"].get("module", "other")
                        ),
                        "value": value,
                    }
                )
            else:
                values[key] = value
        return {"available": True, "values": values, "routes": routes, "reason": ""}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {
            "available": False,
            "values": {},
            "routes": {},
            "reason": "Prometheus no disponible o sin respuesta válida",
        }
