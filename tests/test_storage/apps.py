from django.apps import AppConfig

from tumpara.api import register_subschema


class TestStorageConfig(AppConfig):
    name = "tests.test_storage"

    def ready(self):
        from .api import subschema

        register_subschema(subschema)
