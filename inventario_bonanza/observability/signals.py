from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver


@receiver(user_login_failed, dispatch_uid="bonanza_auth_failures")
def failed_login(sender, **kwargs):
    from django.conf import settings

    if settings.OBSERVABILITY_ENABLED:
        from .metrics import AUTH_FAILURES

        AUTH_FAILURES.inc()
