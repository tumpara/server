import logging

from django.core.management.base import BaseCommand, CommandParser

from tumpara.storage.models import Library

_logger = logging.getLogger(__name__)


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
        library_count = Library.objects.count()
        if library_count == 0:
            _logger.warning("Could not start scan because no libraries exist.")
            return
        elif library_count == 1:
            _logger.info(f"Starting consecutive scan of {library_count} library...")
        else:
            _logger.info(f"Starting consecutive scan of {library_count} libraries...")

        for library in Library.objects.all():
            library.scan(slow=slow)
