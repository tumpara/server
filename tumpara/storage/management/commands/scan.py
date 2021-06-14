from django.core.management.base import BaseCommand, CommandParser

from tumpara.storage.models import Library


class Command(BaseCommand):
    help = (
        "Performs a full scan in all libraries. This makes sure that the current "
        "media index is up to date with the file system."
    )

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--slow",
            dest="slow",
            action="store_true",
            help="Run a more through scan. This will compare file hashes instead of "
            "only timestamps.",
        )

    def handle(self, *args, slow=False, **kwargs):
        for library in Library.objects.all():
            library.scan(slow=slow)
