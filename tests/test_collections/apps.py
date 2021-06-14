from django.apps import AppConfig

from tumpara.api import register_subschema


class TestCollectionsConfig(AppConfig):
    name = "tests.test_collections"

    def ready(self):
        from .api import subschema

        register_subschema(subschema)
