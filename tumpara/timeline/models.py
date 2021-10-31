from __future__ import annotations

from typing import Iterable, Optional, Union
from uuid import UUID, uuid4

from django.contrib.gis.db import models
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F, Q, QuerySet, Value, functions
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from tumpara.accounts.models import GenericUser, MembershipHost, User
from tumpara.collections.models import Archivable, Collection, CollectionItem
from tumpara.storage.models import (
    File,
    FileHandler,
    Library,
    LibraryContent,
    LibraryContentManager,
)
from tumpara.utils import map_object_to_primary_key, pk_type

__all__ = ["Entry", "Album", "AlbumItem"]


class EntryQuerySet(QuerySet):
    """Custom QuerySet for entry objects that will provide the correct
    implementations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prefetch_related_lookups = ("photo",)

    @staticmethod
    def _get_implementation(obj):
        if obj is None:
            return None
        try:
            return obj.implementation
        except AttributeError:
            return obj

    def __getitem__(self, k):
        result = super().__getitem__(k)
        if isinstance(result, models.Model):
            return self._get_implementation(result)
        elif isinstance(result, list):
            return [self._get_implementation(obj) for obj in result]
        else:
            return result

    def __iter__(self):
        for item in super().__iter__():
            try:
                yield item.implementation
            except AttributeError:
                yield item

    def get(self, *args, **kwargs):
        return self._get_implementation(super().get(*args, **kwargs))


class EntryManager(LibraryContentManager):
    def with_stack_size(
        self, user: GenericUser, queryset: Optional[QuerySet] = None
    ) -> QuerySet:
        if queryset is None:
            queryset = self.get_queryset()
        elif not issubclass(queryset.model, self.model):
            raise ValueError(
                f"Cannot annotate a queryset from a different model (got "
                f"{queryset.model!r}, expected {self.model!r} or subclass)."
            )
        if "_stack_size" in queryset.query.annotations:
            return queryset

        stack_size = (
            self.for_user(user)
            .filter(
                library=models.OuterRef("library"),
                stack_key=models.OuterRef("stack_key"),
            )
            .values("stack_key")
            .annotate(count=models.Count("pk"))
            .values("count")
        )

        return queryset.annotate(
            _stack_size=models.Case(
                # For entries which have a stack, we calculate that stack's size as an
                # annotation. This can be used by clients to see if there are more
                # entries to this one.
                models.When(
                    condition=models.Q(stack_key__isnull=False),
                    then=models.Subquery(stack_size),
                ),
                # If there is no stack, imply a size of one.
                default=Value(1),
            )
        )

    @staticmethod
    def _bulk_visibility_check_query() -> Q:
        return Q(file__isnull=True) | Q(file__orphaned=False)

    def stack(
        self,
        objects: Iterable[Union[Entry, UUID]],
        *,
        requester: Optional[GenericUser] = None,
    ):
        """Stack the given objects together.

        :param objects: The objects to stack, either as model instances or by their
            primary keys.
        :param requester: An optional user. If this user does not have write permissions
            on the entries an exception will be raised.
        """
        objects = list(objects)

        if len(objects) < 2:
            raise ValueError(
                "To stack timeline entries, you need to provide at least two objects."
            )

        if requester is not None:
            if not self.bulk_check_visibility(requester, objects, writing=True):
                raise PermissionDenied(
                    "Either one or more items in the provided set of entries does not "
                    "exist or you do not have permission to alter them."
                )

        primary_keys = [
            map_object_to_primary_key(item, self.model, "timeline entry stacking")
            for item in objects
        ]

        # Update the stack keys so the provided objects are on the same stack. What we
        # need to do here:
        # 1) Find all the stacks that contain at least one of the provided objects -
        #    these are the stacks that will be relevant later.
        # 2) Find a key for the stack that will be set. This is either one of the ones
        #    we discovered before, or the next free one.
        # 3) Update the stack key for all applicable entries. This includes both those
        #    provided by the caller and those in the existing stacks (since we want to
        #    merge them).
        with transaction.atomic():
            object_details = self.filter(pk__in=primary_keys).values_list(
                "library__pk", "stack_key"
            )

            library_pks = {item[0] for item in object_details}
            if len(library_pks) > 1:
                # The reason we only allow stacking inside a single library is because
                # we need to ensure that the entire stack is visible to exactly the same
                # set of users. Since libraries can have different memberships we make
                # sure that a stack can't span those.
                raise ValueError(
                    "Stacking is only allowed for entries inside the same library."
                )

            relevant_stack_keys = {item[1] for item in object_details} - {None}

            if len(relevant_stack_keys) == 0:
                # If none of the objects is in a stack yet, we need a new key. This will
                # be the next available one. In order to avoid race conditions, we use
                # a subquery here.
                new_stack_key = RawSQL(
                    "SELECT COALESCE(MAX(stack_key) + 1, 1) FROM timeline_entry", ()
                )
            else:
                # If we already have an existing stack, we can use a key from there.
                new_stack_key = next(iter(relevant_stack_keys))

            queryset = self.filter(
                Q(pk__in=primary_keys) | Q(stack_key__in=relevant_stack_keys)
            )
            queryset.update(
                stack_key=new_stack_key,
                # Make the first item that was provided the representative. All others
                # will be "demoted".
                stack_representative=models.Case(
                    models.When(pk=primary_keys[0], then=Value(True)),
                    default=Value(False),
                ),
                # Make sure the visibility is the same for all entries. This is
                # required so that users that can see any single item in the stack
                # will always be able to see at least the representative. The value
                # we choose for the visibility is the maximum of all candidates -
                # which translates to the most secure one in use. That means stacking
                # will only ever make entries more private, but never more public.
                visibility=models.Subquery(
                    queryset
                    # Using .order_by() with empty arguments here to remove the initial
                    # ordering by timestamp:
                    .order_by()
                    # This trick with the dummy variable is from here:
                    # https://stackoverflow.com/a/64902200
                    # It removes the unnecessary GROUP BY clause that Django adds
                    # when using .annotate(). This should no longer be required once
                    # this ticket is implemented:
                    # https://code.djangoproject.com/ticket/28296
                    .annotate(dummy=Value(1))
                    .values("dummy")
                    .annotate(new_visibility=models.Max("visibility"))
                    .values("new_visibility"),
                ),
            )

    def bulk_set_visibility(
        self,
        objects: Iterable[Union[models.Model, pk_type]],
        visibility: int,
    ):
        pks: list[pk_type] = [
            map_object_to_primary_key(item, self.model, "bulk visibility setting")
            for item in objects
        ]
        annotated_with_stack = self.annotate(
            library_stack=functions.Concat(
                F("library_id"),
                Value("-"),
                F("stack_key"),
                output_field=models.CharField(),
            )
        )
        qs = annotated_with_stack.filter(
            Q(
                library_stack__in=annotated_with_stack.filter(
                    pk__in=pks, stack_key__isnull=False
                )
                .values("library_stack")
                .distinct()
            )
            | Q(pk__in=pks)
        )
        qs.update(visibility=visibility)


class ActiveEntryManager(EntryManager):
    def get_queryset(self) -> QuerySet:
        return (
            super()
            .get_queryset()
            .filter(Q(file__isnull=True) | Q(file__orphaned=False))
        )

    def stacks_for_user(self, user: GenericUser) -> QuerySet:
        queryset = self.for_user(user).filter(
            Q(stack_representative=True) | Q(stack_key=None)
        )
        queryset = self.with_stack_size(user, queryset)
        return queryset

    def stack(self, *args, **kwargs):
        raise NotImplementedError(
            "Use Entry.objects.stack() instead of using the active_objects manager."
        )


class Entry(Archivable, LibraryContent, library_context="timeline"):
    """This is the base supertype for anything timeline-related.

    The most important attribute an entry has is it's timestamp. Ideally,
    it is derived directly from the medium / metadata itself. If that information
    isn't available, the timestamp should fall back to creation timestamps.

    An entry may also optionally provide geolocation information.

    Important: Entries do not currently support being moved from one library to another.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    created_at = models.DateTimeField(
        _("add timestamp"),
        auto_now_add=True,
        help_text=_("Timestamp when this entry was created / imported."),
    )

    timestamp = models.DateTimeField(
        _("timestamp"),
        default=timezone.now,
        db_index=True,
        help_text=_(
            "Timestamp associated with this entry. For media content, this should be "
            "the date and time of recording."
        ),
    )
    location = models.PointField(
        _("location"),
        null=True,
        blank=True,
        help_text=_("Real-world location associated with this entry."),
    )

    file = models.ForeignKey(
        File,
        verbose_name=_("file"),
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
        help_text=_("The file object associated with this entry, if any."),
    )

    # The reason we don't use a single foreign key that points to the representative
    # directly is because this approach let's us define more precise database
    # constraints (see the Meta class below).
    stack_key = models.IntegerField(
        _("stack key"),
        null=True,
        blank=True,
        default=None,
        help_text=_("Identifier that is the same for all entries on a stack."),
    )
    stack_representative = models.BooleanField(
        _("stack representative status"),
        default=False,
        help_text=_(
            "Designates whether this entry is it's stack's representative. It "
            "will be shown as the cover element when the stack is rendered."
        ),
    )

    objects = EntryManager()
    active_objects = ActiveEntryManager.from_queryset(EntryQuerySet)()

    class Meta:
        verbose_name = _("timeline entry")
        verbose_name_plural = _("timeline entries")
        ordering = ["timestamp", "id"]
        indexes = [
            models.Index(
                fields=("timestamp", "id", "visibility", "library", "file"),
                name="timeline_for_user_idx",
            ),
            models.Index(
                fields=("-timestamp", "id", "visibility", "library", "file"),
                name="reverse_timeline_for_user_idx",
            ),
            models.Index(
                fields=("stack_key", "id", "visibility", "library", "file"),
                name="stack_content_for_user_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("stack_key", "stack_representative"),
                condition=Q(stack_representative=True),
                name="unique_representative_per_stack",
            ),
            models.CheckConstraint(
                check=Q(stack_key__isnull=False) | Q(stack_representative=False),
                name="not_a_representative_when_unstacked",
            ),
        ]
        default_manager_name = "active_objects"

    @cached_property
    def implementation(self) -> Entry:
        """Return the actual implementation of this entry, depending on it's type."""
        # Find all related types that are subclasses of Entry. These are iterated to
        # find out which one is the correct one in this case.
        result = self
        for relation in self._meta.related_objects:
            if not isinstance(relation, models.OneToOneRel):
                continue
            if not issubclass(relation.related_model, Entry):
                continue
            try:
                result = getattr(self, relation.name)
                break
            except relation.related_model.DoesNotExist:
                pass

        if result is not self:
            # If this entry has been annotated with a stack size, keep it.
            if hasattr(self, "_stack_size"):
                result._stack_size = self._stack_size

        # If no appropriate subclass was found, just return self again.
        return result

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            del self._stack_size
        except AttributeError:
            pass

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        try:
            del self._stack_size
        except AttributeError:
            pass

    def check_visibility(self, *args, **kwargs):
        if self.file is not None and self.file.orphaned:
            return False
        return super().check_visibility(*args, **kwargs)

    def clear_stack(self, *, requester: Optional[GenericUser] = None):
        """Clear this entry's stack. This will remove all entries from the stack (not
        just this one.

        :param requester: An optional user. If this user does not have write permissions
            on the entry an exception will be raised.
        """
        if requester is not None and not self.check_visibility(requester, writing=True):
            raise PermissionDenied("You do not have permission to unstack this entry.")
        if self.stack_key is None:
            return
        # Note that we directly use Entry.objects instead of type(self).objects here
        # because we want to find all entries in the stack and not just those with this
        # object's type.
        Entry.objects.filter(library=self.library_id, stack_key=self.stack_key).update(
            stack_key=None, stack_representative=False
        )

        self.refresh_from_db()

    def unstack(self, *, requester: Optional[GenericUser] = None):
        """Remove this entry from it's stack. This will keep other in the stack.

        :param requester: An optional user. If this user does not have write permissions
            on the entry an exception will be raised.
        """
        if requester is not None and not self.check_visibility(requester, writing=True):
            raise PermissionDenied("You do not have permission to unstack this entry.")

        if self.stack_size < 3:
            return self.clear_stack()

        if self.stack_representative:
            # Since this entry is the representative, we need to find a new one. The
            # representative can't be an orphaned file and we would prefer it to not
            # be archived, but if we can't find any other that's okay as well.
            new_representative = (
                Entry.objects.filter(
                    Q(library=self.library_id, stack_key=self.stack_key)
                    & ~Q(pk=self.pk)
                    & (Q(file__isnull=True) | Q(file__orphaned=False))
                )
                .order_by("archived", "-timestamp")
                .first()
            )
            if new_representative is None:
                # If there is no candidate for the representative, clear the stack.
                self.clear_stack()
            else:
                self.stack_key = None
                self.stack_representative = False
                new_representative.stack_representative = True

                self.save()
                new_representative.save()
        else:
            self.stack_key = None
            self.save()

    @property
    def stack_size(self):
        # The _stack_size attribute is set by the StackingEntryManager. If we can't
        # obtain the information from there, we have to fetch it ourselves.
        try:
            return self._stack_size
        except AttributeError:
            if self.stack_key is None:
                return 1

            self._stack_size = Entry.active_objects.filter(
                stack_key=self.stack_key
            ).count()
            return self._stack_size

    def set_visibility(self, visibility: int, *, save: bool = True):
        """Set this entry's visibility.

        Calling this method will make sure that visibility settings inside the stack
        (if any) are kept consistent.
        """
        if self.stack_key is not None:
            Entry.objects.filter(library=self.library, stack_key=self.stack_key).update(
                visibility=visibility
            )
            self.refresh_from_db()
        else:
            self.visibility = visibility
            if save:
                self.save()


class Album(Collection, MembershipHost, Archivable):
    """A user-created collection of timeline entries."""

    items = models.ManyToManyField(
        Entry,
        through="AlbumItem",
        related_name="containing_albums",
        related_query_name="containing_album",
    )
    name = models.CharField(
        _("name"), max_length=150, help_text=_("Collection title given by the user.")
    )

    class Meta:
        verbose_name = _("collection")
        verbose_name_plural = _("collections")


class AlbumItem(CollectionItem):
    collection = models.ForeignKey(
        Album,
        on_delete=models.CASCADE,
        verbose_name=_("collection"),
        help_text=_("The timeline collection the entry is placed in."),
    )
    entry = models.ForeignKey(
        Entry,
        on_delete=models.CASCADE,
        verbose_name=_("entry"),
        help_text=_("The timeline entry associated with this object."),
    )

    @property
    def content_object(self) -> Entry:
        return self.entry.implementation

    @content_object.setter
    def content_object(self, obj: Entry):
        self.entry = obj
