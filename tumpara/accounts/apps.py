from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from tumpara.api import register_subschema


class AccountsConfig(AppConfig):
    name = "tumpara.accounts"
    verbose_name = _("Accounts")

    def ready(self):
        from .api.schema import subschema

        register_subschema(subschema)
