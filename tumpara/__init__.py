import os

try:
    from graphene_types.utils import patch_object_type

    # Patch the Graphene ObjectType so we can use the generic version:
    # https://github.com/whtsky/graphene-types#installation
    patch_object_type()
except ImportError:
    pass


def execute_management_from_command_line():
    from django.core import management

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tumpara.settings.production")
    management.execute_from_command_line()
