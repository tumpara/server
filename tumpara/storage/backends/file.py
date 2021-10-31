import logging
import os
from collections import deque
from urllib.parse import ParseResult

import inotify_simple
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from inotify_simple import flags as inotify_flags
from inotifyrecursive import Event as INotifyEvent
from inotifyrecursive import INotify

from .. import register_library_backend
from .base import LibraryBackend

__all__ = ["FileSystemBackend"]
_logger = logging.getLogger(__name__)


@register_library_backend("file")
class FileSystemBackend(LibraryBackend, FileSystemStorage):
    def __init__(self, parsed_uri: ParseResult):
        FileSystemStorage.__init__(self, parsed_uri.path)

    def check(self):
        if not os.path.exists(self.base_location):
            raise ValidationError(
                f"The specified path {self.base_location} does not exist."
            )
        if not os.path.isdir(self.base_location):
            raise ValidationError(
                f"The specified path {self.base_location} is not a directory."
            )

    def watch(self):
        from ..scanner.events import (
            FileModifiedEvent,
            FileMovedEvent,
            FileRemovedEvent,
            FolderMovedEvent,
            FolderRemovedEvent,
            NewFileEvent,
        )

        inotify = INotify()
        watch = inotify.add_watch_recursive(
            self.base_location,
            inotify_flags.CREATE
            | inotify_flags.DELETE
            | inotify_flags.MODIFY
            | inotify_flags.MOVED_FROM
            | inotify_flags.MOVED_TO,
        )
        # TODO Inotify provides another flag DELETE_SELF that should be handled somehow.

        def decode_event(event: INotifyEvent) -> tuple[str, list[inotify_flags], str]:
            """Decode an inotify event into the corresponding path (relative to the
            library root) and flags.
            """
            absolute_path = os.path.join(inotify.get_path(event.wd), event.name)
            path = os.path.relpath(absolute_path, self.base_location)

            flags = inotify_flags.from_mask(event.mask)

            return path, flags, absolute_path

        def generator():
            response = 0

            while response is not False:
                # This generator may take a special value that is only used in tests
                # as input from send(). It checks if the inotify backend has any more
                # events. If it does not, it yields True to indicate so.
                if response == "check_empty":  # pragma: no cover
                    # Use the inotify_simple API here because inotifyrecursive
                    # doesn't proxy the timeout parameter.
                    events = inotify_simple.INotify.read(inotify, timeout=0)
                    events = filter(
                        lambda event: event.mask & inotify_flags.IGNORED == 0, events
                    )
                    events = list(events)
                    if len(events) == 0:
                        response = yield True
                    else:
                        response = yield events

                    continue

                # Take a timeout value from the input. This is also used inside tests.
                events = deque(
                    inotify.read(
                        timeout=response if isinstance(response, int) else None
                    )
                )

                if len(events) == 0:
                    yield None

                while response is not False and len(events) > 0:
                    event = events.popleft()
                    path, flags, absolute_path = decode_event(event)
                    if len(events) > 0:
                        next_event = events[0]
                        next_path, next_flags, next_absolute_path = decode_event(
                            next_event
                        )
                    else:
                        next_path, next_flags, next_absolute_path = None, [], None

                    if inotify_flags.MOVED_FROM in flags:
                        # For MOVED_FROM events, check if the next event is a
                        # corresponding MOVED_TO event. If so, then a file or folder
                        # was moved inside the library.
                        if inotify_flags.MOVED_TO in next_flags:
                            if (
                                inotify_flags.ISDIR in flags
                                and inotify_flags.ISDIR in next_flags
                            ):
                                # A folder was moved inside of the library.
                                events.popleft()
                                response = yield FolderMovedEvent(
                                    old_path=path, new_path=next_path
                                )
                                continue
                            elif (
                                inotify_flags.ISDIR not in flags
                                and inotify_flags.ISDIR not in next_flags
                                and os.path.isfile(next_absolute_path)
                            ):
                                # A file was moved inside of the library.
                                events.popleft()
                                response = yield FileMovedEvent(
                                    old_path=path, new_path=next_path
                                )
                                continue
                            else:
                                # The next event had nothing to do with the current
                                # one. This state should not actually happen.
                                # TODO: Raise a warning here.
                                pass

                        # A file or folder was moved out of the library.
                        if inotify_flags.ISDIR in flags:
                            response = yield FolderRemovedEvent(path=path)
                        else:
                            response = yield FileRemovedEvent(path=path)
                    elif inotify_flags.MOVED_TO in flags:
                        if inotify_flags.ISDIR in flags:
                            for filename in self.walk_files(path):
                                response = yield NewFileEvent(path=filename)
                                if response is False:  # pragma: no cover
                                    break
                        elif os.path.isfile(absolute_path):
                            response = yield NewFileEvent(path=path)
                    elif inotify_flags.CREATE in flags:
                        if inotify_flags.ISDIR not in flags and os.path.isfile(
                            absolute_path
                        ):
                            # When creating and directly saving a file, two inotify
                            # events may be received - a CREATE and a MODIFY event.
                            # If this is the case, the latter event is scrapped so
                            # the client only receives a NewFileEvent doesn't get an
                            # additional FileModifiedEvent following it.
                            if (
                                inotify_flags.ISDIR not in next_flags
                                and inotify_flags.MODIFY in next_flags
                                and next_path == path
                            ):
                                events.popleft()
                            response = yield NewFileEvent(path=path)
                    elif inotify_flags.MODIFY in flags:
                        if inotify_flags.ISDIR not in flags and os.path.isfile(
                            absolute_path
                        ):
                            response = yield FileModifiedEvent(path=path)
                    elif inotify_flags.DELETE in flags:
                        if inotify_flags.ISDIR not in flags:
                            response = yield FileRemovedEvent(path=path)
                    else:  # pragma: no cover
                        _logger.warning(
                            f"Received an inotify event that could not be handled ("
                            f"path {path}, mask {event.mask}). This is probably a bug."
                        )

            try:
                inotify.rm_watch_recursive(watch)
            except OSError:
                pass
            return None

        return generator()
