from support.permissions import is_platform_admin


def can_monitor(user):
    return (
        user.is_authenticated
        and user.is_active
        and (
            is_platform_admin(user)
            or (
                user.organization_id is None
                and user.has_perm("observability.view_monitoring")
            )
        )
    )


def can_configure(user):
    return can_monitor(user) and (
        is_platform_admin(user) or user.has_perm("observability.configure_monitoring")
    )
