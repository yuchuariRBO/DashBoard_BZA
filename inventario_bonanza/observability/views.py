import secrets

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import caches
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from support.models import Priority, Status, SupportAudit
from support.permissions import is_agent, queue_for

from .metrics import registry
from .models import AlertIncident, AlertRule
from .permissions import can_configure, can_monitor
from .prometheus import performance, valid_base
from .snapshot import prometheus_snapshot, snapshot

cache = caches["monitoring"]


DASHBOARDS = {
    "general": ("bonanza-general", "Estado general"),
    "django": ("bonanza-django", "Django y APIs"),
    "database": ("bonanza-database", "Base de datos"),
    "services": ("bonanza-services", "Servicios"),
    "support": ("bonanza-support", "Mesa de ayuda"),
}


@require_GET
def metrics(request):
    token = settings.MONITOR_METRICS_TOKEN
    expected = "Bearer " + token
    provided = request.headers.get("Authorization", "")
    authenticated = bool(
        token and secrets.compare_digest(provided.encode(), expected.encode())
    )
    if not authenticated and not can_monitor(request.user):
        return HttpResponse("Acceso restringido", status=403)
    content = generate_latest(registry())
    try:
        content += prometheus_snapshot()
    except DatabaseError:
        content += b"# HELP bonanza_database_available Consulta de salud\n# TYPE bonanza_database_available gauge\nbonanza_database_available 0\n"
    for service in cache.get("bonanza_service_health", []):
        # Names originate in a fixed allowlist in sample_monitoring.
        name = service["name"]
        if name not in ("minio", "people_api", "plates_api"):
            continue
        content += f'bonanza_service_available{{service="{name}"}} {int(service["up"])}\nbonanza_service_duration_seconds{{service="{name}"}} {service["duration"]}\n'.encode()
    response = HttpResponse(content, content_type=CONTENT_TYPE_LATEST)
    response["Cache-Control"] = "no-store"
    return response


@login_required
def dashboard(request):
    if not can_monitor(request.user):
        raise PermissionDenied
    data = snapshot()
    perf = cache.get("bonanza_performance")
    if perf is None:
        perf = performance()
        cache.set("bonanza_performance", perf, 15)
    incidents = (
        AlertIncident.objects.select_related("rule")
        .prefetch_related("events")
        .order_by("-first_seen")[:100]
    )
    active = AlertIncident.objects.filter(
        resolved_at__isnull=True, detected_at__isnull=False
    ).count()
    return render(
        request,
        "observability/dashboard.html",
        {
            "data": data,
            "performance": perf,
            "performance_metrics": [
                (label, perf["values"].get(key))
                for key, label in [
                    ("rps", "Solicitudes por segundo"),
                    ("rpm", "Solicitudes por minuto"),
                    ("mean", "Duración promedio (s)"),
                    ("p50", "Latencia P50 (s)"),
                    ("p95", "Latencia P95 (s)"),
                    ("p99", "Latencia P99 (s)"),
                    ("errors_4xx", "Errores 4xx por segundo"),
                    ("errors_5xx", "Proporción de errores 5xx"),
                    ("concurrent", "Solicitudes en curso"),
                    ("workers", "Trabajadores instrumentados"),
                    ("saturation", "Saturación aproximada"),
                    ("auth_failures", "Fallos de acceso en 15 min"),
                    ("qps", "Consultas SQL por segundo"),
                    ("db_errors", "Errores SQL en 5 min"),
                ]
            ],
            "infrastructure_metrics": [
                (label, data["infrastructure"].get(key))
                for key, label in [
                    ("cpu_percent", "CPU (%)"),
                    ("memory_percent", "Memoria (%)"),
                    ("disk_percent", "Disco (%)"),
                    ("uptime_seconds", "Tiempo encendido (s)"),
                ]
            ],
            "reported_tickets": queue_for(request.user).select_related(
                "requester", "category", "assignee"
            )[:10]
            if is_agent(request.user)
            else [],
            "ticket_summary": [
                {
                    "status": dict(Status.choices).get(row["status"], row["status"]),
                    "priority": dict(Priority.choices).get(
                        row["priority"], row["priority"]
                    ),
                    "total": row["total"],
                }
                for row in data["tickets"]
            ],
            "incidents": incidents,
            "active_alerts": active,
            "services": cache.get("bonanza_service_health"),
            "grafana_configured": bool(
                settings.GRAFANA_URL and valid_base(settings.GRAFANA_URL)
            ),
            "grafana_dashboards": DASHBOARDS,
            "activity_window": settings.MONITOR_ACTIVE_WINDOW_SECONDS,
            "configure_allowed": can_configure(request.user),
        },
    )


@login_required
def grafana(request, slug):
    if not can_monitor(request.user):
        raise PermissionDenied
    if (
        slug not in DASHBOARDS
        or not settings.GRAFANA_URL
        or not valid_base(settings.GRAFANA_URL)
    ):
        raise Http404
    return redirect(settings.GRAFANA_URL.rstrip("/") + "/d/" + DASHBOARDS[slug][0])


class RuleForm(forms.ModelForm):
    class Meta:
        model = AlertRule
        fields = ["threshold", "hold_seconds", "severity", "enabled"]
        widgets = {
            name: forms.NumberInput(attrs={"class": "form-control"})
            for name in ["threshold", "hold_seconds"]
        }


@login_required
def rules(request):
    if not can_configure(request.user):
        raise PermissionDenied
    forms_list = [
        (rule, RuleForm(instance=rule, prefix=str(rule.pk)))
        for rule in AlertRule.objects.all()
    ]
    if request.method == "POST":
        rule = get_object_or_404(AlertRule, pk=request.POST.get("pk"))
        form = RuleForm(request.POST, instance=rule, prefix=str(rule.pk))
        if form.is_valid():
            with transaction.atomic():
                form.save()
                SupportAudit.objects.create(
                    actor=request.user,
                    action="monitor_rule_changed",
                    object_label=rule.name,
                    changes=form.cleaned_data,
                )
            messages.success(request, "Regla actualizada.")
            return redirect("observability:rules")
        forms_list = [(r, form if r.pk == rule.pk else f) for r, f in forms_list]
    return render(request, "observability/rules.html", {"rule_forms": forms_list})


@require_GET
def grafana_access(request):
    """Nginx auth_request: identity headers only after Django authorization."""
    from support.permissions import is_platform_admin

    if not request.user.is_authenticated:
        return HttpResponse(status=401)
    if not can_monitor(request.user):
        return HttpResponse(status=403)
    response = HttpResponse(status=204)
    response["X-Grafana-User"] = request.user.username
    response["X-Grafana-Role"] = (
        "Admin" if is_platform_admin(request.user) else "Viewer"
    )
    response["Cache-Control"] = "no-store"
    return response
