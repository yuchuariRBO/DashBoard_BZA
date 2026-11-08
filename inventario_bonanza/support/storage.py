from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateSupportStorage(FileSystemStorage):
    """Never use the existing public media/MinIO proxy for support documents."""

    def __init__(self):
        super().__init__(
            location=settings.SUPPORT_PRIVATE_ROOT,
            base_url=None,
            file_permissions_mode=0o600,
            directory_permissions_mode=0o700,
        )

    def url(self, name):
        raise ValueError("Los adjuntos se descargan desde la vista autorizada.")
