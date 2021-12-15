import abc
import os
from collections import deque
from functools import partial
from typing import Generator
from urllib.parse import ParseResult

from django.core.files.storage import Storage

from ..scanner import EventGenerator

__all__ = ["LibraryBackend"]


class LibraryBackend(Storage, abc.ABC):
    """Base class for storage backends used by :class:`storage.models.Library` objects.

    This is a refinement of Django's storage engine, providing additional methods
    related to scanning.
    """

    @abc.abstractmethod
    def __init__(self, parsed_uri: ParseResult):
        """Initialize the backend.

        This method should parse the given URI and set any required model fields.

        :param parsed_uri: The parsed source URI of the library.
        """
        raise NotImplementedError(
            "subclasses of LibraryBackend must provide a constructor"
        )

    @abc.abstractmethod
    def check(self) -> None:
        """Check the backend's configuration and return whether it is valid and usable.

        :raises ValidationError: When the backend is misconfigured or the
            remote service cannot be reached (if applicable).
        """
        raise NotImplementedError(
            "subclasses of LibraryBackend must provide a check() method"
        )

    def walk_files(
        self, start_directory: str = "", *, safe: bool = True
    ) -> Generator[str, None, None]:
        """Generator that yields the names of all files in this backend.

        The default implementation iterates through all directories and yields
        filenames appropriately.

        :param start_directory: Optional starting directory. Use this to only iterate
            over a subfolder.
        :param safe: Set this to False to raise IO errors when they encounter.
        """
        if not isinstance(start_directory, str):
            raise TypeError("Expected a string as the starting directory.")
        paths = deque([start_directory])

        while len(paths) > 0:
            current_path = paths.pop()

            try:
                directories, files = self.listdir(current_path)
            except IOError:  # pragma: no cover
                if safe:
                    continue
                else:
                    raise

            paths.extend(map(partial(os.path.join, current_path), directories))
            for filename in files:
                yield os.path.join(current_path, filename)

    def watch(self) -> EventGenerator:
        """Generator that yields events on changes. This may not be supported by all
        backends.

        Send `False` to this generator to stop watching and return. Doing so will
        raise a `StopIteration` Exception.

        :raises NotImplementedError: If this backend does not support watching for
            file changes.
        """
        raise NotImplementedError(
            "This library backend does not support watching files."
        )
