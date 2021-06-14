from django.apps import AppConfig

from tumpara.api import register_subschema


class TestApiConfig(AppConfig):
    name = "tests.test_api"

    def ready(self):
        from .api import subschema

        register_subschema(subschema)
