from __future__ import annotations

import hashlib
import logging
import os
from functools import partial
from os import path
from typing import Iterable, Optional, Type, Union
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from tumpara.accounts.models import GenericUser, MembershipHost, User
from tumpara.utils import map_object_to_primary_key, pk_type

from . import file_handlers, library_backends, scanner
from .backends.base import LibraryBackend

__all__ = [
    "InvalidFileTypeError",
    "Visibility",
    "Library",
    "LibraryContentManager",
    "LibraryContent",
    "File",
    "FileHandler",
]
_logger = logging.getLogger(__name__)


class InvalidFileTypeError(Exception):
    pass


class Visibility:
    PUBLIC = 0
    INTERNAL = 1
    MEMBERS = 2
    OWNERS = 3

    VISIBILTY_CHOICES = [
        (PUBLIC, _("Public")),
        (INTERNAL, _("All logged-in users")),
        (MEMBERS, _("Library members")),
        (OWNERS, _("Only library owners")),
    ]


def validate_library_source(source: str):
    parsed_source = urlparse(source)

    if parsed_source.scheme not in library_backends:
        raise ValidationError(
            f"No supported library backend configured for source scheme "
            f"{parsed_source.scheme!r}."
        )

    backend: LibraryBackend = library_backends[parsed_source.scheme](parsed_source)
    backend.check()


class Library(MembershipHost, Visibility):
    """A source entity used to retrieve files.

    Everything that Tumpara manages lives in a library somewhere - currently,
    the only available source for such a library is a folder on disk.
    """

    source = models.CharField(
        _("source"),
        unique=True,
        max_length=255,
        validators=[validate_library_source],
        help_text=_("URI for the configured storage backend."),
    )
    context = models.CharField(
        _("context"),
        max_length=50,
        help_text=_(
            "Context string that identifies the content types to expect in the library."
        ),
    )

    default_visibility = models.PositiveSmallIntegerField(
        _("default visibility"),
        choices=Visibility.VISIBILTY_CHOICES,
        default=Visibility.MEMBERS,
        help_text=_("Default visibility value for content where it is not defined."),
    )

    class Meta:
        verbose_name = _("library")
        verbose_name_plural = _("libraries")

    def __str__(self):
        return f"<Library at {self.source!r}>"

    @cached_property
    def backend(self) -> LibraryBackend:
        """Return the configured :class:`LibraryBackend` for accessing files."""
        parsed_source = urlparse(self.source)

        if parsed_source.scheme not in library_backends:
            raise RuntimeError(
                f"No supported library backend configured for source scheme"
                f" {parsed_source.scheme!r}."
            )

        return library_backends[parsed_source.scheme](parsed_source)

    def get_handler_type(self, path: str) -> Optional[Type[FileHandler]]:
        """Return the handle type for a file at a given path inside this library."""
        assert (
            self.context in file_handlers and len(file_handlers[self.context]) > 0
        ), f"no file handlers registered for context {self.context}"

        for handler_type in file_handlers[self.context]:
            try:
                handler_type.analyze_file(self, path)
                return handler_type
            except InvalidFileTypeError:
                continue

        return None

    def scan(
        self,
        watch: bool = False,
        *,
        thread_count: int = None,
        **kwargs,
    ):
        """Perform a scan of this library, making sure that all records are up to date.

        The full scan process occurs in two steps. First, existing entries on record
        are checked, testing whether the actual file on disk is still available. Any
        File objects that are not accessible are marked as `orphaned`. Later,
        if a new file is found with the hash of an orphaned database entry, the entry
        will be linked to the new file location. Second, the actual filesystem scan
        is performed. This emits :class:`.scanner.events.FileModifiedEvent` events
        for every found file. This event will delegate handling to
        :class:`.scanner.events.NewFileEvent` for files that are not on record yet.

        Optionally, a watch stage can be run after the full scan. This stage polls
        for changes to the library backend and updates the database as needed.

        It is recommended to run :func:`clean_orphans` after performing a full scan
        to remove no longer needed database entries.

        :param watch: Whether to continue to watch for changes after the initial scan
            has been completed.
        :param thread_count: Number of processes to use for event handling. `None` will
            automatically choose.
        :param kwargs: Additional flags that will be passed on to handlers.
        """
        from .scanner.events import FileModifiedEvent
        from .scanner.runner import run

        _logger.info(f"Scanning existing content in {self} for changes...")
        scan_timestamp = timezone.now()
        file_queue = set()
        processed_count = 0

        for file in self.files.filter(orphaned=False):
            if file.needs_rescan(**kwargs):
                file.orphaned = True
            else:
                file.last_scanned = scan_timestamp
            file_queue.add(file)

            if len(file_queue) > 100:
                self.files.bulk_update(file_queue, ("last_scanned", "orphaned"))
                processed_count += len(file_queue)
                file_queue.clear()

                if (
                    processed_count > 0
                    and processed_count % settings.REPORT_INTERVAL < 100
                ):
                    _logger.info(f"Processed {processed_count} database entries.")

        self.files.bulk_update(file_queue, ("last_scanned", "orphaned"))
        _logger.info(f"Finished existing content scan. Running file scan for {self}.")

        def events() -> scanner.EventGenerator:
            for path in self.backend.walk_files(safe=True):
                yield FileModifiedEvent(path=path)

            if watch:
                _logger.info(
                    f"Finished file scan for {self}. Continuing to watch for changes."
                )
                # When watching, pass through all events from the backend's
                # EventGenerator. The response needs to be handled separately to
                # support stopping the generator.
                generator = self.backend.watch()
                response = None
                while response is not False:
                    response = yield generator.send(response)
                try:
                    generator.send(False)
                except StopIteration:
                    pass
            else:
                _logger.info(f"Finished scan for {self}.")

        run(self, events(), thread_count=thread_count, **kwargs)

    def clean_orphans(self):
        """Clean all orphaned file objects still on record."""
        self.files.filter(orphaned=True).delete()


def validate_library(context: str, library_pk: int):
    library = Library.objects.get(pk=library_pk)
    if library.context != context:
        raise ValidationError(
            _("the specified library is not configured to use the correct context")
        )


class LibraryContentManager(models.Manager):
    def for_user(self, user: GenericUser, *, writing: bool = False) -> QuerySet:
        """Return a queryset containing only objects that a given user is allowed to
        see.

        :param user: The user that is logged in. This will determine the scope of
            permissions.
        :param writing: If this is set, only items where the user has write access are
            returned.
        """
        queryset = self.get_queryset()

        def visibility_query(visibility: int):
            return Q(visibility=visibility) | Q(
                visibility=self.model.INFERRED, library__default_visibility=visibility
            )

        if user.is_authenticated and not user.is_active:
            return queryset.none()

        if not user.is_authenticated:
            if writing:
                return queryset.none()
            else:
                return queryset.filter(visibility_query(self.model.PUBLIC))
        if user.is_superuser:
            return queryset

        user_libraries_owned = Library.objects.for_user(user, ownership=True)

        if writing:
            return queryset.filter(library__in=user_libraries_owned)
        else:
            user_libraries_not_owned = Library.objects.for_user(user, ownership=False)
            return queryset.filter(
                visibility_query(self.model.PUBLIC)
                | visibility_query(self.model.INTERNAL)
                | (
                    visibility_query(self.model.MEMBERS)
                    & Q(library__in=user_libraries_not_owned)
                )
                | Q(library__in=user_libraries_owned)
            )

    @staticmethod
    def _bulk_visibility_check_query() -> Q:
        return Q()

    def bulk_check_visibility(
        self,
        user: GenericUser,
        objects: Iterable[Union[models.Model, pk_type]],
        *,
        writing: bool = False,
    ):
        if user.is_superuser:
            return True

        pks: list[pk_type] = [
            map_object_to_primary_key(item, self.model, "bulk visibility checking")
            for item in objects
        ]
        return self.for_user(user, writing=writing).filter(
            Q(pk__in=pks) & self._bulk_visibility_check_query()
        ).count() == len(pks)

    def bulk_set_visibility(
        self,
        objects: Iterable[Union[models.Model, pk_type]],
        visibility: int,
    ):
        pks: list[pk_type] = [
            map_object_to_primary_key(item, self.model, "bulk visibility setting")
            for item in objects
        ]
        self.filter(pk__in=pks).update(visibility=visibility)


class LibraryContent(models.Model, Visibility):
    """Base model for objects that are logically contained in a library.

    This model provides a four-tier permission system: an item is either public,
    internal, member-only or owner-only. This determines who can see it. The last two
    choices depend on whether the user is added to the corresponding library.
    """

    INFERRED = None

    library = models.ForeignKey(
        Library,
        verbose_name=_("library"),
        on_delete=models.CASCADE,
        help_text=_(
            "Library the object is attached to. Users will have access depending on "
            "the visibility and their membership in this library."
        ),
    )
    visibility = models.PositiveSmallIntegerField(
        _("visibility"),
        choices=[
            *Visibility.VISIBILTY_CHOICES,
            (INFERRED, _("Default value for library")),
        ],
        null=True,
        default=None,
        help_text=_("Determines who can see this object."),
    )

    objects = LibraryContentManager()

    class Meta:
        abstract = True

    def __init_subclass__(cls, /, library_context: Optional[str] = None, **kwargs):
        if library_context is not None:
            # Add a validator to the library field to ensure that only libraries with
            # the appropriate handle app are valid.
            cls.library.field._validators.append(
                partial(validate_library, library_context)
            )

        super().__init_subclass__(**kwargs)

    @property
    def actual_visibility(self):
        """The actually active visibility value, which may be inferred from the
        library.
        """
        return (
            self.visibility
            if self.visibility is not self.INFERRED
            else self.library.default_visibility
        )

    def set_visibility(self, visibility: Optional[int], *, save: bool = True):
        """Set this item's visibility."""
        self.visibility = visibility
        if save:
            self.save()

    def check_visibility(self, user: GenericUser, *, writing: bool = False):
        """Check whether this object is visible for a given user.

        :param user: The user in question.
        :param writing: If this is set, ``True`` will only be returned if the user is
            allowed to make changes to the object.
        """
        if not writing and self.actual_visibility == self.PUBLIC:
            return True
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
        if not writing and self.actual_visibility == self.INTERNAL:
            return True

        membership = self.library.get_membership_for_user(user)
        if membership is None:
            return False

        if not writing and self.actual_visibility == self.MEMBERS:
            return True
        return membership.is_owner


class File(models.Model):
    """A file found in a library.

    This model describes files that were found while scanning - it doesn't do
    anything else. A :class:`FileHandler` object provided by the other apps actually
    does something with it.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    library = models.ForeignKey(
        Library,
        verbose_name=_("library"),
        on_delete=models.CASCADE,
        related_name="files",
        related_query_name="file",
    )

    path = models.CharField(
        _("filename"),
        max_length=255,
        help_text=_("Path of this file, relative to the library root."),
    )
    digest = models.CharField(
        _("digest value"),
        max_length=64,
        help_text="The file's cryptographic hash to quickly identify changes.",
    )
    last_scanned = models.DateTimeField(
        _("scan timestamp"),
        null=True,
        blank=True,
        help_text="Time the file was last scanned. This is used to determine changes.",
    )

    orphaned = models.BooleanField(
        _("orphaned status"),
        default=False,
        help_text="Whether this database entry is an orphan and could be deleted "
        "because the file on disk is gone.",
    )

    handler_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    handler_object_id = models.UUIDField()
    handler = GenericForeignKey("handler_content_type", "handler_object_id")

    class Meta:
        verbose_name = _("file")
        verbose_name_plural = _("files")
        constraints = [
            models.UniqueConstraint(
                fields=["library", "path"],
                condition=models.Q(orphaned=False),
                name="active_path_unique_in_library",
            ),
        ]
        indexes = [
            models.Index(
                fields=("library", "path", "orphaned"), name="library_path_lookup_idx"
            ),
            models.Index(
                fields=("library", "digest", "orphaned"),
                name="library_digest_lookup_idx",
            ),
        ]

    @property
    def folder_name(self):
        """Name of the folder the file is stored in, relative to the library root."""
        return os.path.dirname(self.path)

    def __str__(self):
        return f"{self.path} in {self.library}"

    def _calculate_digest(self) -> str:
        hasher = hashlib.blake2b(digest_size=32)
        with self.open("rb") as content:
            hasher.update(content.read())
        return hasher.hexdigest()

    def scan(self, slow: bool = False, **kwargs):
        """Re-scan this file for changes.

        This tests if it's hash still matches the one on record. If the file isn't
        found, this record is marked as orphaned. If the hash has changed,
        it is re-scanned.

        :param slow: Denotes whether a slow scan should be performed. In that case, the
            file's hash is recalculated to check for changes. Otherwise just the
            timestamp is used.
        """
        if not self.library.backend.exists(self.path):
            # If the file is no longer present, bail out an mark it as orphaned.
            self.orphaned = True
            self.save()
            return

        # Check if the file has changed - either using the hash or timestamp.
        if slow:
            current_hash = self._calculate_digest()
            changed = current_hash != self.digest
        else:
            # See the comment in needs_rescan() for infos on why we need to look at
            # both timestamps here.
            changed_at = max(
                self.library.backend.get_modified_time(self.path),
                self.library.backend.get_modified_time(path.dirname(self.path)),
            )
            changed = self.last_scanned is None or self.last_scanned < changed_at

        if not changed:
            self.orphaned = False
            self.last_scanned = timezone.now()
        else:
            # Since the file was changed, scan it again.
            try:
                self.handler.analyze_file(self.library, self.path)
            except InvalidFileTypeError:
                # Orphan because the current handler has an incorrect type.
                self.orphaned = True
            else:
                self.orphaned = False

                if "current_hash" not in locals():
                    current_hash = self._calculate_digest()
                self.digest = current_hash

                # This little dance with the handler reference somehow mitigates an
                # IntegrityError with newly created file objects because self.handler
                # becomes None after calling save() on the handler. Only after saving
                # the handler does it receive a primary key, and after assigning it
                # again the content type fields get populated (which would throw the
                # aforementioned error if they are empty).
                handler = self.handler
                self.handler.scan_from_file(slow=slow, **kwargs)
                self.handler = handler

                self.last_scanned = timezone.now()

        self.save()

    def needs_rescan(self, slow: bool = False, **kwargs) -> bool:
        """Check whether this file's records still match the file on disk.

        This will not re-scan the entire file or commit any changes to the model. It
        only checks whether the content in the storage backend have been changed since
        the last time this file was scanned.

        :param slow: If this is ``True``, contents will be compared using file hashes.
            Otherwise change timestamps will be used.
        :returns: ``True`` if the file on disk may have changed since the last scan.
            This does not mean that it has to have happened. For example, if a new file
            is created in a folder, all sibling files will be handled as changed as
            well. This is because of how POSIX filesystems handle move changes (see the
            comments in the code for details). ``False`` is returned when there is no
            indication that the file needs rescan.
        """
        if self.last_scanned is None:
            return True
        if not self.library.backend.exists(self.path):
            return True
        if slow:
            return self._calculate_digest() != self.digest
        else:
            # Instead of only looking at the file's timestamp, we also have to check the
            # parent folder's modified time, because we want to catch files that got
            # moved. See here the last point here for details why this is necessary:
            # https://unix.stackexchange.com/a/503236
            changed_at = max(
                self.library.backend.get_modified_time(self.path),
                self.library.backend.get_modified_time(path.dirname(self.path)),
            )
            return self.last_scanned < changed_at

    def open(self, *args, **kwargs):
        """Return a file handler for the file's source.

        This is a proxy method to the library backend that handles storage.
        """
        return self.library.backend.open(self.path, *args, **kwargs)


class FileHandler(models.Model):
    """A file handler is a concrete class that does something with a file."""

    file = models.ForeignKey(
        File,
        verbose_name=_("file"),
        on_delete=models.CASCADE,
        related_name="+",
        help_text=_("File object this handler is responsible for."),
    )

    class Meta:
        abstract = True

    def scan_from_file(self, **kwargs):
        """Callback for file updates.

        This method is called when :func:`File.scan` detects a change on disk for the
        file. It is also called once when the handler is first initializes. Any
        business logic like scanning metadata should happen here.

        Note: Subclasses should call `.save()` after performing their scan.

        :param kwargs: Mix of options passed to the :func:`Library.scan` method and
            additional arguments received from :func:`analyze_file`.
        """
        raise NotImplementedError(
            "subclasses of FileHandler must provide a scan_from_file() method"
        )

    @classmethod
    def analyze_file(cls, library: Library, path: str):
        """Analyze a file and check whether this is the correct handler.

        If the given file is not applicable for this type of handler,
        an :exc:`InvalidFileTypeError` should be raised. In that case the next handler
        will be tested.

        :param library: Library the file is in.
        :param path: File path in the library.
        :raises InvalidFileTypeError: When the given file does not match this
            handler implementation.
        """
        raise NotImplementedError(
            "subclasses of FileHandler must provide an analyze_file() method"
        )
