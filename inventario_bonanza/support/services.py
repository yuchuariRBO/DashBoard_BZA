from contextlib import contextmanager
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    Attachment,
    Comment,
    Notification,
    Priority,
    SLAPolicy,
    Status,
    Ticket,
    TicketEvent,
)
from .permissions import can_work, is_agent, manages_support

TRANSITIONS = {
    Status.OPEN: {Status.REVIEW, Status.PROGRESS, Status.WAITING},
    Status.REVIEW: {Status.PROGRESS, Status.WAITING, Status.RESOLVED},
    Status.PROGRESS: {Status.REVIEW, Status.WAITING, Status.RESOLVED},
    Status.WAITING: {Status.REVIEW, Status.PROGRESS, Status.RESOLVED},
    Status.RESOLVED: {Status.CLOSED, Status.OPEN},
    Status.CLOSED: {Status.OPEN},
}


class Conflict(ValidationError):
    pass


@contextmanager
def ticket_transaction():
    saved = []
    try:
        with transaction.atomic():
            yield saved
    except Exception:
        for storage, name in saved:
            storage.delete(name)
        raise


def attach(ticket, actor, upload, saved, comment=None):
    if not upload:
        return
    from .forms import validate_attachment

    validate_attachment(upload)
    item = Attachment(
        ticket=ticket,
        uploaded_by=actor,
        comment=comment,
        name=upload.name[:180],
        size=upload.size,
        content_type=upload.support_content_type,
    )
    item.file.save(upload.name, upload, save=False)
    saved.append((item.file.storage, item.file.name))
    item.save()


def notify(ticket, actor, text):
    recipients = {ticket.requester_id, ticket.assignee_id} - {None, actor.pk}
    Notification.objects.bulk_create(
        [
            Notification(recipient_id=pk, ticket=ticket, message=text)
            for pk in recipients
        ]
    )


def event(ticket, actor, kind, details=None, internal=False):
    TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        kind=kind,
        details=details or {},
        staff_only=internal,
    )


def apply_policy(ticket, now):
    policy = SLAPolicy.objects.filter(priority=ticket.priority).first()
    ticket.reopen_days = policy.reopen_days if policy else 7
    ticket.response_due_at = None
    ticket.resolution_due_at = None
    if policy and policy.enabled:
        ticket.response_due_at = ticket.created_at + timedelta(
            hours=policy.response_hours
        )
        ticket.resolution_due_at = now + timedelta(hours=policy.resolution_hours)


def claim(ticket, version):
    if (
        Ticket.objects.filter(pk=ticket.pk, version=version).update(
            version=F("version") + 1, updated_at=timezone.now()
        )
        != 1
    ):
        raise Conflict(
            "El ticket cambió mientras lo editaba. Recargue la página y vuelva a intentarlo."
        )
    ticket.version = version + 1


def create_ticket(actor, data):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied
    with ticket_transaction() as saved:
        ticket = Ticket.objects.create(
            requester=actor,
            organization_id=actor.organization_id,
            subject=data["subject"],
            description=data["description"],
            category=data["category"],
        )
        apply_policy(ticket, ticket.created_at)
        ticket.save(
            update_fields=["response_due_at", "resolution_due_at", "reopen_days"]
        )
        event(ticket, actor, "created", {"status": ticket.get_status_display()})
        attach(ticket, actor, data.get("attachment"), saved)
    return ticket


def add_comment(actor, ticket, data):
    with ticket_transaction() as saved:
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        staff = can_work(actor, ticket)
        if ticket.requester_id != actor.pk and not staff:
            raise PermissionDenied
        if data.get("internal") and not staff:
            raise PermissionDenied
        if ticket.status == Status.CLOSED:
            raise ValidationError("Reabra el ticket antes de comentar.")
        claim(ticket, data["version"])
        comment = Comment.objects.create(
            ticket=ticket,
            author=actor,
            body=data["body"],
            internal=bool(data.get("internal")),
        )
        if (
            staff
            and actor.pk != ticket.requester_id
            and not comment.internal
            and not ticket.first_response_at
        ):
            ticket.first_response_at = timezone.now()
            ticket.save(update_fields=["first_response_at"])
        event(
            ticket,
            actor,
            "internal_note" if comment.internal else "comment",
            internal=comment.internal,
        )
        attach(ticket, actor, data.get("attachment"), saved, comment)
        if not comment.internal:
            notify(ticket, actor, "Nueva respuesta en su solicitud de soporte.")
    return ticket


def update_ticket(actor, ticket, data, requester_action=False):
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        staff = can_work(actor, ticket)
        desired = data["status"]
        if (
            desired not in Status.values
            or data.get("priority", ticket.priority) not in Priority.values
        ):
            raise ValidationError("Estado o prioridad inválidos.")
        if requester_action:
            if ticket.requester_id != actor.pk:
                raise PermissionDenied
            if desired == Status.CLOSED and ticket.status != Status.RESOLVED:
                raise ValidationError("Solo puede confirmar un ticket resuelto.")
            if desired == Status.OPEN:
                since = ticket.resolved_at or ticket.closed_at
                if (
                    ticket.status not in (Status.RESOLVED, Status.CLOSED)
                    or not since
                    or timezone.now() > since + timedelta(days=ticket.reopen_days)
                ):
                    raise ValidationError(
                        "El plazo para reabrir este ticket terminó o su estado no permite reabrirlo."
                    )
            elif desired != Status.CLOSED:
                raise PermissionDenied
        elif not staff:
            raise PermissionDenied
        if desired != ticket.status and desired not in TRANSITIONS[ticket.status]:
            raise ValidationError("La transición de estado no está permitida.")
        claim(ticket, data["version"])
        if not requester_action:
            if "assignee" in data and data["assignee"] != ticket.assignee:
                if not manages_support(actor):
                    raise PermissionDenied
                agent = data["assignee"]
                if agent and not is_agent(agent):
                    raise ValidationError(
                        "El responsable no está habilitado como agente."
                    )
                if (
                    agent
                    and agent.organization_id
                    and agent.organization_id != ticket.organization_id
                ):
                    raise ValidationError("El agente pertenece a otra organización.")
                old = str(ticket.assignee or "Sin asignar")
                ticket.assignee = agent
                event(
                    ticket,
                    actor,
                    "assigned",
                    {"before": old, "after": str(agent or "Sin asignar")},
                    internal=True,
                )
            if data.get("priority", ticket.priority) != ticket.priority:
                old = ticket.get_priority_display()
                ticket.priority = data["priority"]
                apply_policy(ticket, ticket.created_at)
                event(
                    ticket,
                    actor,
                    "priority",
                    {"before": old, "after": ticket.get_priority_display()},
                )
        if desired != ticket.status:
            old = ticket.get_status_display()
            ticket.status = desired
            if desired == Status.RESOLVED:
                ticket.resolved_at = timezone.now()
            if desired == Status.CLOSED:
                ticket.closed_at = timezone.now()
            if desired == Status.OPEN:
                ticket.resolved_at = None
                ticket.closed_at = None
                apply_policy(ticket, timezone.now())
            event(
                ticket,
                actor,
                "status",
                {"before": old, "after": ticket.get_status_display()},
            )
        ticket.save()
        notify(ticket, actor, f"Solicitud actualizada: {ticket.get_status_display()}.")
    return ticket
