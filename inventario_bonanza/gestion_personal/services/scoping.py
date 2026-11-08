"""Reglas de alcance por organización."""

from django.db.models import Q

from ..models import Person


def organization_filter_for(user):
    """Devuelve el filtro de organización visible para el usuario indicado."""
    if getattr(user, 'user_type', None) == 'global_admin' and not getattr(user, 'organization_id', None):
        return Q()
    if getattr(user, 'organization_id', None):
        return Q(organization_id=user.organization_id)
    return Q(organization__isnull=True)


def people_for_user(user):
    """Consulta base de personas autorizadas para el usuario."""
    return Person.objects.filter(organization_filter_for(user))


def person_by_id_number_for_user(user, id_number):
    return people_for_user(user).filter(id_number=id_number).first()


def organization_records_for(model, user):
    """Unassigned records are visible only to the system administrator."""
    queryset = model.objects.all()
    if user.is_authenticated and user.user_type == 'global_admin' and user.organization_id is None:
        return queryset
    if user.is_authenticated and user.organization_id:
        return queryset.filter(organization_id=user.organization_id)
    return queryset.none()
