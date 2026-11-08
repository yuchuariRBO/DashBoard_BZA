from .permissions import is_agent, is_platform_admin, manages_support


def module_access(request):
    user = request.user
    return {
        "support_agent": is_agent(user),
        "support_manager": manages_support(user),
        "platform_admin": is_platform_admin(user),
        "support_configurator": manages_support(user) and user.organization_id is None,
        "monitoring_admin": user.is_authenticated
        and user.is_active
        and (
            is_platform_admin(user)
            or (
                user.organization_id is None
                and user.has_perm("observability.view_monitoring")
            )
        ),
    }
