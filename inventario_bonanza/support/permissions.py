from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Ticket


def is_platform_admin(user):
    return (
        user.is_authenticated
        and user.is_active
        and (
            user.is_superuser
            or (user.user_type == "global_admin" and user.organization_id is None)
        )
    )


def manages_support(user):
    return (
        user.is_authenticated
        and user.is_active
        and (is_platform_admin(user) or user.has_perm("support.manage_support"))
    )


def is_agent(user):
    return (
        user.is_authenticated
        and user.is_active
        and (manages_support(user) or user.has_perm("support.work_ticket"))
    )


def queue_for(user):
    qs = Ticket.objects.all()
    if not user.is_authenticated or not user.is_active:
        return qs.none()
    if not is_platform_admin(user):
        if manages_support(user) or user.has_perm("support.view_queue"):
            if user.organization_id:
                qs = qs.filter(
                    Q(organization_id=user.organization_id) | Q(requester=user)
                )
        else:
            assigned = Q(assignee=user)
            if user.organization_id:
                assigned &= Q(organization_id=user.organization_id)
            return qs.filter(
                Q(requester=user) | (assigned if is_agent(user) else Q(pk__in=[]))
            )
    return qs


def can_work(user, ticket):
    if not is_agent(user):
        return False
    if (
        user.organization_id
        and ticket.organization_id != user.organization_id
        and not is_platform_admin(user)
    ):
        return False
    return (
        manages_support(user)
        or user.has_perm("support.view_queue")
        or ticket.assignee_id == user.pk
    )


def agents_for(user):
    qs = (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(
            Q(is_superuser=True)
            | Q(user_type="global_admin", organization__isnull=True)
            | Q(
                user_permissions__codename="work_ticket",
                user_permissions__content_type__app_label="support",
            )
            | Q(
                groups__permissions__codename="work_ticket",
                groups__permissions__content_type__app_label="support",
            )
        )
    )
    if user.organization_id and not is_platform_admin(user):
        qs = qs.filter(
            Q(organization_id=user.organization_id) | Q(organization__isnull=True)
        )
    return qs.distinct()
