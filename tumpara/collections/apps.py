from django.apps import AppConfig

from tumpara.api import register_subschema


class CollectionsConfig(AppConfig):
    name = "tumpara.collections"

    def ready(self):
        from .api.schema import subschema

        register_subschema(subschema)
