from functools import partial
from typing import Any, Callable, Generator

import graphene
from django.db.models import Count, Q
from django.db.models import functions as model_functions
from django.db.models.query import QuerySet
from graphene import relay
from graphene_django import DjangoConnectionField
from graphql_relay.connection.arrayconnection import cursor_to_offset, offset_to_cursor

from tumpara.api.filtering import FilterSet
from tumpara.collections.api import ArchivableFilterSet, CollectionsFilter
from tumpara.storage.api import LibraryContentFilterSet

from .. import models
from .albums import Album
from .entry_filtersets import entry_filtersets
from .types import TimelineEntryInterface


class EntryFilterSetBase(ArchivableFilterSet, LibraryContentFilterSet):
    """Options to filter a timeline view."""

    albums = CollectionsFilter(
        description="Options that narrow down results based on whether items are or "
        "are not in the specified albums."
    )
    types = graphene.List(
        graphene.NonNull(graphene.String),
        description="Entry types to return. This should be a list of GraphQL type "
        "names. If this is empty or null, no types will be filtered out.",
    )

    @property
    def _type_filtersets(self) -> Generator[tuple[FilterSet, str], None, None]:
        for graphql_type_name, (model_properties, _) in entry_filtersets.items():
            property_name = model_properties[0]
            if self.types and graphql_type_name not in self.types:
                continue

            type_filterset: FilterSet = getattr(self, f"{property_name}_filters")
            yield type_filterset, model_properties

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        """Filter a given queryset according to the rules defined in this filter set.

        This method will respect all registered filter sets that are defined for
        specific entry types, although they will only match when the corresponding
        type is actually requested in the `types` field.
        """

        type_queries = Q()

        # Merge all Q objects from the individual types. Each sub-filterset here is
        # supposed to return the query that should be applied to all objects of it's
        # type (other types should be ignored). All these Q objects are OR-ed together.
        for type_filterset, model_properties in self._type_filtersets:
            type_prefixes = (f"{prefix}{name}__" for name in model_properties)
            if not type_filterset:
                # If a type_filterset is empty or has an empty query (see below),
                # a blanket __isnull query is added in it's place. This makes sure
                # that objects of this type don't get dropped even though they were
                # requested in self.types.
                for type_prefixes in type_prefixes:
                    type_queries |= Q(**{f"{type_prefixes}isnull": False})
                continue

            for type_prefix in type_prefixes:
                type_query = type_filterset.build_query(info, type_prefix)
                if len(type_query) == 0:
                    type_query = Q(**{f"{type_prefix}isnull": False})
                type_queries |= type_query

        query = super().build_query(info, prefix)
        query &= ArchivableFilterSet.build_query(self, info, prefix)

        # type_queries is a Q object consisting of a set of disjunctions that find
        # exactly the selected entry types. This is AND-ed together with the rest of
        # the top-level filters.
        query &= type_queries

        if self.albums is not None:
            query &= self.albums.build_query(
                info,
                f"{prefix}containing_album",
                models.Album,
                Album,
            )

        return query

    def prepare_queryset(self, queryset: QuerySet, prefix: str = "") -> QuerySet:
        for type_filterset, model_properties in self._type_filtersets:
            if not type_filterset:
                continue

            for model_property in model_properties:
                queryset = type_filterset.prepare_queryset(
                    queryset, prefix=f"{prefix}{model_property}__"
                )
        return queryset


EntryFilterSet = type(
    "TimelineEntryFilterSet",
    (EntryFilterSetBase, FilterSet),
    {
        f"{model_properties[0]}_filters": graphene.Field(
            filterset_class,
            description=f"Filter options for specific entry types. These will be "
            f"applied to all results of type {graphql_type_name}.",
        )
        for graphql_type_name, (
            model_properties,
            filterset_class,
        ) in entry_filtersets.items()
    },
)


class TimelineEntryConnection(relay.Connection):
    class Meta:
        node = TimelineEntryInterface

    class Edge:
        index = graphene.Int(
            required=True,
            description="Index of this item in the view. This can be used for "
            "offset-based pagination.",
        )

        @staticmethod
        def resolve_index(parent, info: graphene.ResolveInfo):
            return cursor_to_offset(parent.cursor)


class TimelineEntryConnectionField(DjangoConnectionField):
    """Custom connection field that correctly handles the abstract types of timeline
    elements."""

    def __init__(self, type=TimelineEntryConnection, *args, **kwargs):
        kwargs.setdefault("enforce_first_or_last", True)
        kwargs.setdefault("max_limit", 500)
        super().__init__(type, *args, **kwargs)

    @property
    def type(self):
        return super(relay.ConnectionField, self).type

    @property
    def model(self):
        return models.Entry

    @classmethod
    def resolve_queryset(
        cls, connection_type, queryset: QuerySet, info: graphene.ResolveInfo, args
    ) -> QuerySet:
        return queryset


class TimelineViewMonthBucket(graphene.ObjectType):
    """Item distribution bucket for a month of data in a timeline view.

    This object provides two cursors that can be used for pagination in the `entries`
    query from the corresponding TimelineView. These respect the sorting order.
    """

    month = graphene.Int(required=True, description="Month number (between 1 and 12)")
    total_entry_count = graphene.Int(
        required=True,
        description="Total number of timeline entries on record for this month.",
    )
    start_cursor = graphene.String(
        required=True,
        description="Cursor that can be used for pagination the start of this bucket. "
        "This will be the cursor of the element the would come directly before the "
        "first element in this set.",
    )
    end_cursor = graphene.String(
        required=True,
        description="Cursor that can be used for pagination from the end of this "
        "bucket. Similarly to the `startCursor` field, this is the cursor of the "
        "element after the last item in this set.",
    )

    @staticmethod
    def resolve_start_cursor(parent: dict, info: graphene.ResolveInfo) -> str:
        return offset_to_cursor(parent["start_index"] - 1)

    @staticmethod
    def resolve_end_cursor(parent: dict, info: graphene.ResolveInfo) -> str:
        return offset_to_cursor(parent["end_index"] + 1)


class TimelineViewYearBucket(graphene.ObjectType):
    """Item distribution bucket for a year of data in a timeline view."""

    year = graphene.Int(required=True, description="Year number")
    total_entry_count = graphene.Int(
        required=True,
        description="Total number of timeline entries on record for this year.",
    )
    month_distribution = graphene.List(
        TimelineViewMonthBucket,
        required=True,
        description="Detailed records for each month in this year.",
    )


class TimelineView(graphene.ObjectType):
    """Wrapper for timeline-related queries.

    This is the unmounted object type. See :class:`TimelineViewField` for the
    mountable field.
    """

    entries = TimelineEntryConnectionField(
        description="All entries in this timeline view."
    )
    year_distribution = graphene.List(
        TimelineViewYearBucket,
        description="Data distribution by time. This can be used to render timelines / "
        "scrollbars. Only available when sorting by time.",
    )

    # The first parameter in these resolve methods (which would normally be parent or
    # root) is the queryset returned from TimelineViewField's resolver. It is the
    # queryset the view is based on.

    @staticmethod
    def resolve_entries(
        queryset: QuerySet, info: graphene.ResolveInfo, **kwargs
    ) -> QuerySet:
        return queryset

    @staticmethod
    def resolve_year_distribution(
        queryset: QuerySet, info: graphene.ResolveInfo
    ) -> dict:
        assert isinstance(
            queryset, QuerySet
        ), "No QuerySet received from the parent TimelineView."

        if len(queryset.query.order_by) > 0 and queryset.query.order_by[0] not in (
            "timestamp",
            "-timestamp",
            "+timestamp",
        ):
            raise ValueError(
                "Cannot build the chronological distribution for the required query. "
                "The first ordering criteria must be the timestamp."
            )

        reversed_timeline = (
            len(queryset.query.order_by) > 0
            and queryset.query.order_by[0] == "-timestamp"
        )

        queryset = (
            queryset.annotate(
                group=model_functions.TruncMonth("timestamp"),
            )
            .values("group")
            .order_by("-group" if reversed_timeline else "group")
            .annotate(count=Count("pk"))
        )
        distribution = []

        current_year = None
        current_index = 0
        for row in queryset:
            if row["group"] is None:
                # TODO It seems that invalid dates (before unix epoch) return None for
                #   the annotated 'group' field - at least under SQLite. We should
                #   handle that somehow.
                continue

            year = row["group"].strftime("%Y")
            month = row["group"].strftime("%m")
            count = row["count"]

            if current_year and current_year["year"] != year:
                current_year["total_entry_count"] = sum(
                    map(
                        lambda i: i["total_entry_count"],
                        current_year["month_distribution"],
                    )
                )
                distribution.append(current_year)
                current_year = None

            if current_year is None:
                current_year = {"year": year, "month_distribution": []}

            end_index = current_index + count - 1
            current_year["month_distribution"].append(
                {
                    "month": month,
                    "total_entry_count": count,
                    "start_index": current_index,
                    "end_index": end_index,
                }
            )
            current_index = end_index

        if current_year is not None:
            current_year["total_entry_count"] = sum(
                map(
                    lambda i: i["total_entry_count"],
                    current_year["month_distribution"],
                )
            )
            distribution.append(current_year)

        return distribution


class TimelineViewField(graphene.Field):
    """Wrapper for timeline-related queries.

    This is the mountable field that will return :class:`TimelineView` object types.
    When resolving it, return a Django queryset of timeline Entry objects:

    >>> def resolve_timeline(parent, info):
    ...     return Entry.active_objects.get_queryset()
    """

    def __init__(self, *args, **kwargs):
        # Add arguments
        kwargs.setdefault(
            "filters",
            EntryFilterSet(
                description="Filters to narrow down results inside this view."
            ),
        )
        kwargs.setdefault(
            "reverse",
            graphene.Boolean(
                default_value=False,
                description="By default, the timeline is sorted chronologically, "
                "returning the oldest entries first. This switch will reverse the "
                "order in which results are passed.",
            ),
        )

        super().__init__(TimelineView, *args, **kwargs)

    @classmethod
    def resolve_view(
        cls,
        parent_resolver: Callable[[Any, graphene.ResolveInfo], QuerySet],
        root,
        info: graphene.ResolveInfo,
        filters: EntryFilterSet = None,
        reverse: bool = False,
        **kwargs,
    ) -> dict:
        """Resolve the view.

        Views are represented by a queryset of timeline Entry objects.
        """
        queryset = parent_resolver(root, info)
        assert isinstance(
            queryset, QuerySet
        ), "The resolver for TimelineViewField did not return a QuerySet."

        if reverse:
            queryset = queryset.order_by("-timestamp", "id")

        if not filters:
            filters = EntryFilterSet._meta.container()

        query = filters.build_query(info)
        # Filter out all entries with orphaned files.
        query &= Q(file__isnull=True) | Q(file__orphaned=False)

        queryset = filters.prepare_queryset(queryset).filter(query)

        for model_properties, _ in entry_filtersets.values():
            queryset = queryset.select_related(*model_properties)

        return queryset

    def get_resolver(
        self,
        parent_resolver: Callable[[Any, graphene.ResolveInfo], QuerySet],
    ):
        return partial(self.resolve_view, parent_resolver)
