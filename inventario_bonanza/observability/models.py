from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class UserActivity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_seen = models.DateTimeField(db_index=True)


class AlertRule(models.Model):
    SIGNALS = [
        ("service_down", "Servicio no disponible"),
        ("errors_5xx", "Tasa HTTP 5xx"),
        ("latency_p95", "Latencia P95"),
        ("cpu", "CPU ocupada"),
        ("memory", "Memoria usada"),
        ("disk", "Disco usado"),
        ("db_slow", "Consultas lentas"),
        ("db_errors", "Errores de base de datos"),
        ("tasks_failed", "Consultas en cola fallidas"),
        ("critical_tickets", "Tickets críticos"),
    ]
    name = models.CharField(max_length=100, unique=True)
    signal = models.CharField(max_length=32, choices=SIGNALS)
    threshold = models.FloatField(default=1, validators=[MinValueValidator(0)])
    hold_seconds = models.PositiveIntegerField(default=300)
    severity = models.CharField(
        max_length=10,
        choices=[("warning", "Advertencia"), ("critical", "Crítica")],
        default="warning",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        permissions = [
            ("view_monitoring", "Acceder al centro de monitoreo"),
            ("configure_monitoring", "Configurar reglas de monitoreo"),
        ]


class AlertIncident(models.Model):
    rule = models.ForeignKey(AlertRule, on_delete=models.PROTECT)
    service = models.CharField(max_length=80, default="platform")
    first_seen = models.DateTimeField()
    detected_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField()
    severity = models.CharField(max_length=10)
    value = models.FloatField(default=0)

    class Meta:
        ordering = ["-first_seen"]
        constraints = [
            models.UniqueConstraint(
                fields=["rule", "service"],
                condition=models.Q(resolved_at__isnull=True),
                name="one_active_monitor_incident",
            )
        ]


class AlertEvent(models.Model):
    incident = models.ForeignKey(
        AlertIncident, on_delete=models.CASCADE, related_name="events"
    )
    kind = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
