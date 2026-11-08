from django.db import migrations


def seed(apps, schema_editor):
    Category = apps.get_model("support", "Category")
    for name in [
        "Problemas de acceso",
        "Errores de la plataforma",
        "Problemas de rendimiento",
        "Problemas con servicios",
        "Problemas con artefactos o archivos",
        "Solicitudes de funcionalidades",
        "Consultas generales",
    ]:
        Category.objects.get_or_create(name=name)
    Policy = apps.get_model("support", "SLAPolicy")
    for priority, response, resolution in [
        ("low", 72, 120),
        ("medium", 24, 72),
        ("high", 4, 24),
        ("critical", 1, 4),
    ]:
        Policy.objects.get_or_create(
            priority=priority,
            defaults={
                "response_hours": response,
                "resolution_hours": resolution,
                "enabled": False,
            },
        )
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    content, _ = ContentType.objects.get_or_create(app_label="support", model="ticket")
    for name, codes in [
        ("Agentes de soporte", ["work_ticket"]),
        ("Administradores de soporte", ["work_ticket", "view_queue", "manage_support"]),
    ]:
        group, _ = Group.objects.get_or_create(name=name)
        for code in codes:
            permission, _ = Permission.objects.get_or_create(
                content_type=content, codename=code, defaults={"name": code}
            )
            group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
