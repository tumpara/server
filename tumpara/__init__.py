import os


def execute_management_from_command_line():
    from django.core import management

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tumpara.settings.production")
    management.execute_from_command_line()
