from django.apps import AppConfig

from tumpara.api import register_subschema


class TestTimelineConfig(AppConfig):
    name = "tests.test_timeline"

    def ready(self):
        from .api import subschema

        register_subschema(subschema)
