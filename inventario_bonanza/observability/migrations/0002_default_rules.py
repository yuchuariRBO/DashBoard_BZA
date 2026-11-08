from django.db import migrations


def seed(apps, schema_editor):
    Rule = apps.get_model("observability", "AlertRule")
    for name, signal, threshold, hold, severity in [
        ("Servicios no disponibles", "service_down", 0, 120, "critical"),
        ("HTTP 5xx superior al 5%", "errors_5xx", 0.05, 300, "critical"),
        ("Latencia P95 superior a 2 s", "latency_p95", 2, 300, "warning"),
        ("CPU superior al 85%", "cpu", 85, 600, "warning"),
        ("Memoria superior al 90%", "memory", 90, 600, "warning"),
        ("Disco superior al 85%", "disk", 85, 600, "warning"),
        ("Más de 0.1 consultas lentas por segundo", "db_slow", 0.1, 300, "warning"),
        ("Errores SQL en los últimos 5 minutos", "db_errors", 0, 120, "critical"),
        ("Más de 3 consultas fallidas recientes", "tasks_failed", 3, 300, "warning"),
        ("Más de 5 tickets críticos abiertos", "critical_tickets", 5, 300, "critical"),
    ]:
        Rule.objects.get_or_create(
            signal=signal,
            defaults={
                "name": name,
                "threshold": threshold,
                "hold_seconds": hold,
                "severity": severity,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("observability", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
