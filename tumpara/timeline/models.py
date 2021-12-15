from __future__ import annotations

from typing import (
    Generic,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    TypeVar,
    Union,
    cast,
    overload,
)
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
    LibraryContentVisibilityType,
)
from tumpara.utils import map_object_to_primary_key, pk_type

__all__ = ["Entry", "Album", "AlbumItem"]


class EntryQuerySet(QuerySet["Entry"]):
    """Custom QuerySet for entry objects that will provide the correct
    implementations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prefetch_related_lookups = ("photo",)

    @overload
    def __getitem__(self, k: int) -> Entry:
        ...

    @overload
    def __getitem__(self, k: slice) -> EntryQuerySet:
        ...

    def __getitem__(self, k: Union[int, slice]) -> Union[Entry, EntryQuerySet]:
        result = super().__getitem__(k)
        if isinstance(result, Entry):
            try:
                return result.implementation
            except AttributeError:
                return result
        elif isinstance(result, EntryQuerySet):
            return result
        else:
            # This skips the case where the result is a list, which is currently not
            # handled upstream:
            # https://github.com/typeddjango/django-stubs/issues/778
            raise TypeError(f"cannot determine type of queryset item: {type(result)}")

    def __iter__(self) -> Iterator[Entry]:
        for item in super().__iter__():
            try:
                yield item.implementation
            except AttributeError:
                yield item

    def get(self, *args, **kwargs) -> Entry:
        obj = super().get(*args, **kwargs)
        try:
            return obj.implementation
        except AttributeError:
            return obj


_Content = TypeVar("_Content", bound="Entry", covariant=True)


class EntryManager(Generic[_Content], LibraryContentManager[_Content]):
    def with_stack_size(
        self,
        user: GenericUser,
        queryset: Optional[QuerySet[_Content]] = None
        # We don't use WithAnnotations as the return type here because MyPy crashes
        # when the generic _Content is the the first parameter here.
        # See also: https://github.com/typeddjango/django-stubs/issues/771
        # Instead, we annotate over the cached property.
    ) -> QuerySet[_Content]:
        """Annotate a queryset with values for the :property:`Entry.stack_size`
        property.

        :param user: User that is used to determine which entries are visible.
        :param queryset: The queryset to annotate. If this is not given, a new one will
            be created.
        """
        if queryset is None:
            queryset = self.get_queryset()
        elif not issubclass(queryset.model, self.model):
            raise ValueError(
                f"Cannot annotate a queryset from a different model (got "
                f"{queryset.model!r}, expected {self.model!r} or subclass)."
            )
        if "stack_size" in queryset.query.annotations:
            return queryset

        stack_size_subquery = models.Subquery(
            # Explicitly using 'Entry.active_objects' and not 'self' here because the
            # stack can contain other entry types as well.
            Entry.active_objects.for_user(user)
            .filter(
                library=models.OuterRef("library"),
                stack_key=models.OuterRef("stack_key"),
            )
            .values("stack_key")
            .annotate(count=models.Count("pk"))
            .values("count")
        )

        annotated_queryset = queryset.annotate(
            # This annotation mirrors what the cached property in the Entry class does:
            # for entries that have a stack, count the total number with the same key.
            # For entries without a stack, imply a size of one.
            stack_size=models.Case(
                models.When(
                    condition=models.Q(stack_key__isnull=False),
                    then=stack_size_subquery,
                ),
                default=Value(1),
            )
        )
        return cast("QuerySet[_Content]", annotated_queryset)

    @staticmethod
    def _bulk_visibility_check_query() -> Q:
        return Q(file__isnull=True) | Q(file__orphaned=False)

    def stack(
        self,
        objects: Iterable[Union[_Content, UUID]],
        *,
        requester: Optional[GenericUser] = None,
    ) -> None:
        """Stack the given entries together.

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

            relevant_stack_keys = [
                item[1] for item in object_details if item[1] is not None
            ]
            new_stack_key: Union[int, RawSQL]

            if len(relevant_stack_keys) == 0:
                # If none of the objects is in a stack yet, we need a new key. This will
                # be the next available one. In order to avoid race conditions, we use
                # a subquery here.
                new_stack_key = RawSQL(
                    "SELECT COALESCE(MAX(stack_key) + 1, 1) FROM timeline_entry", ()
                )
            else:
                # If we already have an existing stack, we can use a key from there.
                new_stack_key = relevant_stack_keys[0]

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
        objects: Iterable[Union[_Content, pk_type]],
        visibility: LibraryContentVisibilityType,
    ) -> None:
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


class ActiveEntryManager(Generic[_Content], EntryManager[_Content]):
    def get_queryset(self) -> QuerySet[_Content]:
        return (
            super()
            .get_queryset()
            .filter(Q(file__isnull=True) | Q(file__orphaned=False))
        )

    def stacks_for_user(self, user: GenericUser) -> QuerySet[_Content]:
        queryset = self.for_user(user).filter(
            Q(stack_representative=True) | Q(stack_key=None)
        )
        queryset = self.with_stack_size(user, queryset)
        return queryset

    def stack(
        self,
        objects: Iterable[Union[_Content, UUID]],
        *,
        requester: Optional[GenericUser] = None,
    ) -> None:
        raise NotImplementedError(
            "Use Entry.objects.stack() instead of using the active_objects manager."
        )


ActiveEntryManagerFromEntryQuerySet = ActiveEntryManager.from_queryset(EntryQuerySet)


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
    active_objects = ActiveEntryManagerFromEntryQuerySet()

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
            if "stack_size" in self.__dict__:
                result.__dict__["stack_size"] = self.__dict__["stack_size"]

        # If no appropriate subclass was found, just return self again.
        return result

    def _invalidate_cached_properties(self) -> None:
        for key in ("implementation", "stack_size"):
            try:
                del self.__dict__[key]
            except AttributeError:
                pass

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        self._invalidate_cached_properties()

    def refresh_from_db(self, *args, **kwargs) -> None:
        super().refresh_from_db(*args, **kwargs)
        self._invalidate_cached_properties()

    def check_visibility(self, *args, **kwargs) -> bool:
        if self.file is not None and self.file.orphaned:
            return False
        return super().check_visibility(*args, **kwargs)

    def clear_stack(self, *, requester: Optional[GenericUser] = None) -> None:
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

    @cached_property
    def stack_size(self) -> int:
        """Size of stack that contains this entry, or ``1`` if it is not on a stack.

        This property will be calculated, unless it the object has been annotated using
        :meth:`EntryManager.with_stack_size`.
        """
        if self.stack_key is None:
            return 1
        else:
            # Explicitly using 'Entry.active_objects' and not 'self.active_objects'
            # because the stack can contain other entry types as well.
            return Entry.active_objects.filter(stack_key=self.stack_key).count()

    def set_visibility(
        self, visibility: LibraryContentVisibilityType, *, save: bool = True
    ):
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


class Album(Collection[Entry], MembershipHost, Archivable):
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


class AlbumItem(CollectionItem[Album]):
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
