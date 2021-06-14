from django.apps import AppConfig

from tumpara.api import register_subschema


class TestAccountsConfig(AppConfig):
    name = "tests.test_accounts"

    def ready(self):
        from .api import subschema

        register_subschema(subschema)
