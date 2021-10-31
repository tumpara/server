from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from tumpara.api import register_subschema


class StorageConfig(AppConfig):
    name = "tumpara.storage"
    verbose_name = _("Storage")
    file_handlers = ["storage.GenericFileHandler"]

    def ready(self):
        from .api.schema import subschema

        register_subschema(subschema)

        if settings.ENABLE_DEMO_BACKEND:
            from .backends import demo  # noqa: F401
