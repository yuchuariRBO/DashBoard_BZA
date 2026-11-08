import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .storage import PrivateSupportStorage


class Category(models.Model):
    name = models.CharField("Nombre", max_length=100, unique=True)
    active = models.BooleanField("Activa", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categorías de soporte"

    def __str__(self):
        return self.name


class Priority(models.TextChoices):
    LOW = "low", "Baja"
    MEDIUM = "medium", "Media"
    HIGH = "high", "Alta"
    CRITICAL = "critical", "Crítica"


class Status(models.TextChoices):
    OPEN = "open", "Abierto"
    REVIEW = "review", "En revisión"
    PROGRESS = "progress", "En proceso"
    WAITING = "waiting", "Pendiente de información"
    RESOLVED = "resolved", "Resuelto"
    CLOSED = "closed", "Cerrado"


class SLAPolicy(models.Model):
    priority = models.CharField(
        "Prioridad", max_length=12, choices=Priority.choices, unique=True
    )
    response_hours = models.PositiveIntegerField(
        "Horas para primera respuesta",
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(8760)],
    )
    resolution_hours = models.PositiveIntegerField(
        "Horas para resolver",
        default=72,
        validators=[MinValueValidator(1), MaxValueValidator(8760)],
    )
    reopen_days = models.PositiveIntegerField(
        "Días para reabrir", default=7, validators=[MaxValueValidator(365)]
    )
    enabled = models.BooleanField("Aplicar SLA", default=False)

    def __str__(self):
        return self.get_priority_display()


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_tickets",
    )
    organization = models.ForeignKey(
        "gestion_personal.Organization", on_delete=models.PROTECT, null=True, blank=True
    )
    subject = models.CharField("Asunto", max_length=180)
    description = models.TextField("Descripción", max_length=20000)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, verbose_name="Categoría"
    )
    priority = models.CharField(
        "Prioridad", max_length=12, choices=Priority.choices, default=Priority.MEDIUM
    )
    status = models.CharField(
        "Estado", max_length=12, choices=Status.choices, default=Status.OPEN
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    reopen_days = models.PositiveIntegerField(default=7)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["requester", "-created_at"]),
            models.Index(fields=["assignee", "status"]),
            models.Index(fields=["resolution_due_at"]),
        ]
        permissions = [
            ("work_ticket", "Atender tickets asignados"),
            ("view_queue", "Consultar cola de soporte autorizada"),
            ("manage_support", "Administrar soporte y configuración"),
        ]

    def __str__(self):
        return f"{self.id} · {self.subject}"

    @property
    def overdue(self):
        return self.status not in (Status.RESOLVED, Status.CLOSED) and bool(
            self.resolution_due_at and self.resolution_due_at < timezone.now()
        )


class Comment(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField("Comentario", max_length=20000)
    internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


def attachment_path(instance, filename):
    return f"{instance.ticket_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Attachment(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="attachments"
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file = models.FileField(storage=PrivateSupportStorage(), upload_to=attachment_path)
    name = models.CharField(max_length=180)
    content_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class TicketEvent(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=32)
    details = models.JSONField(default=dict)
    staff_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_notifications",
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    message = models.CharField(max_length=250)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at"])]


class SupportAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    object_label = models.CharField(max_length=200)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
