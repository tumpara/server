from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from tumpara.api import register_subschema


class GalleryConfig(AppConfig):
    name = "tumpara.content.gallery"
    verbose_name = _("Media Gallery")

    def ready(self):
        from .api.schema import subschema

        register_subschema(subschema)
