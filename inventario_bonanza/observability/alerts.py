from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import AlertEvent, AlertIncident, AlertRule


def evaluate(signals, now=None, service_values=None):
    """None means unknown. One incident per rule/service; no external transports."""
    now = now or timezone.now()
    for rule_id in AlertRule.objects.values_list("pk", flat=True):
        with transaction.atomic():
            rule = AlertRule.objects.select_for_update().get(pk=rule_id)
            if not rule.enabled:
                for incident in AlertIncident.objects.filter(
                    rule=rule, resolved_at__isnull=True
                ):
                    incident.resolved_at = now
                    incident.last_seen = now
                    incident.save()
                    AlertEvent.objects.create(incident=incident, kind="disabled")
                continue
            values = (
                service_values
                if rule.signal == "service_down" and service_values
                else {"platform": signals.get(rule.signal)}
            )
            for service, value in values.items():
                if value is None and rule.enabled:
                    continue
                incident = AlertIncident.objects.filter(
                    rule=rule, service=service, resolved_at__isnull=True
                ).first()
                firing = rule.enabled and value is not None and value > rule.threshold
                if firing:
                    if not incident:
                        incident = AlertIncident.objects.create(
                            rule=rule,
                            service=service,
                            first_seen=now,
                            last_seen=now,
                            severity=rule.severity,
                            value=value,
                        )
                        AlertEvent.objects.create(incident=incident, kind="pending")
                    incident.last_seen = now
                    incident.value = value
                    if (
                        not incident.detected_at
                        and now - incident.first_seen
                        >= timedelta(seconds=rule.hold_seconds)
                    ):
                        incident.detected_at = now
                        AlertEvent.objects.create(incident=incident, kind="firing")
                    incident.save()
                elif incident:
                    incident.resolved_at = now
                    incident.last_seen = now
                    incident.save()
                    AlertEvent.objects.create(
                        incident=incident,
                        kind="resolved" if incident.detected_at else "cleared",
                    )
