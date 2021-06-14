from django.apps import AppConfig

from tumpara.api import Subschema, register_subschema


class TimelineConfig(AppConfig):
    name = "tumpara.timeline"
    file_handlers = ["gallery.Photo"]

    def ready(self):
        def get_subschema() -> Subschema:
            from .api.schema import subschema

            return subschema

        # Defer this subschema so that other apps can register their entry filters
        # first.
        register_subschema(get_subschema)
