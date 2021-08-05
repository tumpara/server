import hashlib
import logging
import os
import re
from dataclasses import dataclass

from django.db import transaction

from ..models import File, Library
from . import BaseEvent

__all__ = [
    "NewFileEvent",
    "FileModifiedEvent",
    "FileMovedEvent",
    "FileRemovedEvent",
    "FolderMovedEvent",
    "FolderRemovedEvent",
]

_logger = logging.getLogger(__name__)


@dataclass
class NewFileEvent(BaseEvent):
    """Event for new files being created.

    This event is both for new files and for files that are moved into the library
    from outside.
    """

    path: str

    def commit(self, library: Library, **kwargs):
        if library.check_path_ignored(self.path):
            _logger.debug(
                f"File {self.path!r} in {library} (new) - skipping because the file is "
                f"in an ignored directory."
            )
            return

        handler_type = library.get_handler_type(self.path)

        if handler_type is None:
            _logger.debug(
                f"File {self.path!r} in {library} (new) - skipping because no "
                f"compatible file handler was found."
            )
            return

        hasher = hashlib.blake2b(digest_size=32)
        with library.backend.open(self.path, "rb") as content:
            hasher.update(content.read())
        file_hash = hasher.hexdigest()

        # Search for orphaned file objects with the same hash. If one exists, try to
        # reclaim it (assuming the handler type still matches).
        try:
            file = library.files.get(digest=file_hash, orphaned=True)
            file.path = self.path
            file.save()
            file.scan()
            if not file.orphaned:
                _logger.debug(
                    f"Re-claiming orphaned hash in {library} for file {self.path!r}."
                )
                return
        except (File.DoesNotExist, File.MultipleObjectsReturned):
            # TODO Handle MultipleObjectsReturned specifically.
            pass

        # Search for orphaned file objects with the same path. If one exists, try to
        # reclaim it (assuming the handler type still matches).
        try:
            file = library.files.get(path=self.path, orphaned=True)
            file.scan()
            if not file.orphaned:
                _logger.debug(f"Re-claiming orphaned file {self.path!r} in {library}.")
                return
        except (File.DoesNotExist, File.MultipleObjectsReturned):
            pass

        _logger.debug(f"Storing new file {self.path} in {library}.")

        with transaction.atomic():
            handler = handler_type()
            try:
                # Save the library to the handler, if the corresponding field exists
                # (not all handlers have it).
                handler.library = library
            except (TypeError, ValueError):
                pass
            file = File(
                library=library,
                path=self.path,
                handler=handler,
            )
            handler.file = file
            file.scan(**kwargs)


@dataclass
class FileModifiedEvent(BaseEvent):
    """Event for files being modified.

    When this event is created for a file that is not yet on record, it will be
    handled like a :class:`NewFileEvent`. The same will be done if the current file's
    type does not match the one on record (aka when the handler types are not the
    same).
    """

    path: str

    def commit(self, library: Library, **kwargs):
        try:
            file = library.files.get(path=self.path, orphaned=False)
        except File.DoesNotExist:
            _logger.debug(
                f"Got a file modified event for {self.path!r} in {library} which is "
                f"not on record. Handling as a new file."
            )
            return NewFileEvent.commit(self, library, **kwargs)

        if library.check_path_ignored(self.path):
            _logger.debug(
                f"Got a file modified event for {self.path!r} in {library}, which is "
                f"in an ignored directory. Marking it as orphaned."
            )
            file.orphaned = True
            file.save()
            return

        if not kwargs.get("slow", False):
            change_timestamp = library.backend.get_modified_time(self.path)
            if file.last_scanned is not None and change_timestamp < file.last_scanned:
                # If the file has not changed, we can skip rescanning it.
                return

        handler_type = library.get_handler_type(self.path)
        if handler_type is not type(file.handler):
            _logger.debug(
                f"Got a file modified event for {self.path!r} in {library}, but the "
                f"handler type on record does not match what was scanned on disk. "
                f"Handling as a new file."
            )
            file.orphaned = True
            file.save()
            return NewFileEvent.commit(self, library, **kwargs)

        file.scan(**kwargs)


@dataclass
class FileMovedEvent(BaseEvent):
    """Event for files being renamed / moved inside of the library."""

    # TODO This could be merged with FolderMovedEvent into a single MoveEvent with
    #  path prefixes as parameters.

    old_path: str
    new_path: str

    def commit(self, library: Library, **kwargs):
        if library.check_path_ignored(self.new_path):
            _logger.debug(
                f"Moving file {self.old_path!r} to {self.new_path!r}, but the new path "
                f"is in an ignored directory. The file will be orphaned."
            )
            library.files.filter(path=self.old_path).update(orphaned=True)
            return

        affected_rows = library.files.filter(path=self.old_path, orphaned=False).update(
            path=self.new_path
        )
        assert (
            affected_rows <= 1
        ), "more than one file was affected by an operation that should be unique"
        if affected_rows == 0:
            _logger.debug(
                f"Got a file moved event for {self.old_path!r} to {self.new_path!r} "
                f"in {library}, but no direct record was available. Handling as a new "
                f"file."
            )
            NewFileEvent(path=self.new_path).commit(library, **kwargs)
        else:
            _logger.debug(f"Moved {self.old_path!r} to {self.new_path!r} in {library}.")


@dataclass
class FileRemovedEvent(BaseEvent):
    """Event for a file being deleted or moved outside of the library."""

    path: str

    def commit(self, library: Library, **kwargs):
        affected_rows = library.files.filter(path=self.path, orphaned=False).update(
            orphaned=True
        )
        assert (
            affected_rows <= 1
        ), "more than one file was affected by an operation that should be unique"
        if affected_rows == 0:
            _logger.debug(
                f"Got a file removed event for {self.path!r} in {library}, but no "
                f"record was available."
            )
        else:
            _logger.debug(f"Removed {self.path} in {library}.")


@dataclass
class FolderMovedEvent(BaseEvent):
    """Event for folders being renamed / moved inside of the library."""

    old_path: str
    new_path: str

    def commit(self, library: Library, **kwargs):
        # The path.join stuff adds an additional slash at the end, making sure really
        # only files inside of the directory are targeted (not that other records should
        # exist, but better safe than sorry). Also, we use regex here because SQLite
        # doesn't support case-sensitive startswith.
        # TODO: Check if we have a case-insensitive filesystem.
        path_regex = "^" + re.escape(os.path.join(self.old_path, ""))

        if library.check_path_ignored(self.new_path):
            _logger.debug(
                f"Moving folder {self.old_path!r} to {self.new_path!r}, but the new "
                f"path is in an ignored directory. Records will be orphaned."
            )
            library.files.filter(path__regex=path_regex).update(orphaned=True)
            return

        count = 0
        # Here, orphaned files are intentionally not filtered out so they are also
        # moved along with other files in the folder. Yay, ghosts :)
        for file in library.files.filter(path__regex=path_regex):
            file.path = os.path.join(
                self.new_path, os.path.relpath(file.path, self.old_path)
            )
            file.save()
            count += 1
        _logger.debug(
            f"Got a folder moved event from {self.old_path!r} to {self.new_path!r} in "
            f"{library} which affected {count} file(s)."
        )


@dataclass
class FolderRemovedEvent(BaseEvent):
    """Event for a folder being deleted or moved outside of the library."""

    path: str

    def commit(self, library: Library, **kwargs):
        # As before, use regex instead of startswith because SQLit doesn't support the
        # latter case-sensitively.
        # TODO: Check if we have a case-insensitive filesystem.
        path_regex = "^" + re.escape(
            os.path.join(self.path, ""),
        )
        affected_rows = library.files.filter(
            path__regex=path_regex, orphaned=False
        ).update(orphaned=True)
        _logger.debug(
            f"Got a folder removed event for {self.path!r} in {library} which affected "
            f"{affected_rows} file(s)."
        )
