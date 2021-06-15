import os.path

from django.conf import settings
from django.utils.timezone import datetime, timezone

from tumpara.storage import register_library_backend
from tumpara.storage.backends import LibraryBackend
from tumpara.storage.scanner import EventGenerator


@register_library_backend("demo")
class DemoBackend(LibraryBackend):
    def __init__(self):
        self.storage_path = os.path.join(settings.DATA_DIR, "demo_backend")

    def check(self):
        pass

    def get_modified_time(self, name):
        # This is datetime.datetime(2001, 4, 19, 4, 25, 21).
        return datetime.utcfromtimestamp(987654321).replace(tzinfo=timezone.utc)

    def watch(self) -> EventGenerator:
        """This backend does not support watching."""
        while True:
            yield None
