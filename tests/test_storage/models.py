from django.db import models

from tumpara.storage import register_file_handler
from tumpara.storage.models import FileHandler, Library, LibraryContent


@register_file_handler(library_context="testing")
class GenericFileHandler(FileHandler):
    """A generic file handler that accepts all files."""

    initialized = models.BooleanField(default=False)
    content = models.BinaryField()

    def scan_from_file(self, **kwargs):
        self.initialized = True
        with self.file.open("rb") as f:
            self.content = f.read()
        self.save()

    @classmethod
    def analyze_file(cls, library: Library, path: str) -> dict:
        pass


class Thing(LibraryContent, library_context="test"):
    pass
