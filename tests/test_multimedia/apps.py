from django.apps import AppConfig

from tumpara.api import register_subschema


class TestMultimediaConfig(AppConfig):
    name = "tests.test_multimedia"

    def ready(self):
        from .api import subschema

        register_subschema(subschema)
