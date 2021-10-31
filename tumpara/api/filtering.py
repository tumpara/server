import graphene
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from graphene_django import DjangoConnectionField, DjangoObjectType
from graphene_django.types import DjangoObjectTypeOptions

__all__ = [
    "FilterSet",
    "FilteredDjangoObjectType",
    "DjangoFilterSetConnectionField",
    "ScalarFilter",
    "NumericFilter",
]


class FilterSet(graphene.InputObjectType):
    """Base class for individual entry type's filter sets.

    This is different from the `graphene_django` filterset class. To use this,
    use a :class:`DjangoFilterSetConnectionField` instead of the usual
    `DjangoFilterConnectionField` that comes with Graphene.
    """

    class Meta:
        abstract = True

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        """Create a Django Q object for this filter set.

        :param info: Graphene resolve information.
        :param prefix: An optional prefix that should be added in front of all
            lookups. This must be given with the trailing double underscore ('__').
        """
        return Q()

    def prepare_queryset(self, queryset: QuerySet, prefix: str = "") -> QuerySet:
        """Prepare a Django QuerySet for filtering.

        Intended use for this method is to annotate required fields onto the queryset.

        :param queryset: The queryset to process.
        :param prefix: An optional prefix that should be added in front of all
            lookups. This must be given with the trailing double underscore ('__').
        :returns: The prepared queryset.
        """
        return queryset


class FilteredDjangoObjectType(DjangoObjectType):
    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, filter_set=None, _meta=None, **options):
        if _meta is None:
            _meta = DjangoObjectTypeOptions(cls)

        if filter_set is not None:
            assert issubclass(
                filter_set, FilterSet
            ), "The 'filter_set' Meta attribute must be a subclass of FilterSet."
        _meta.filter_set = filter_set

        super().__init_subclass_with_meta__(_meta=_meta, **options)


class DjangoFilterSetConnectionField(DjangoConnectionField):
    """Graphene Field that handles a custom filter set.

    To use this field, set the `filter_set` attribute in the DjangoObjectType's
    `Meta` class to the corresponding implementation of :class:`FilterSet`. Note that
    this does not support the filter sets that come with Graphene (or django-filter).
    """

    def __init__(self, *args, filter_set_type=None, **kwargs):
        if filter_set_type is None:
            object_type = args[0]
            if callable(object_type):
                object_type = object_type()

            try:
                filter_set_type = object_type._meta.filter_set
            except AttributeError:
                raise TypeError(
                    "To use DjangoFilterSetConnectionField, the type must provide a"
                    "FilterSet instance in it's Meta class. Alternatively (especially "
                    "when providing the object type in a callable) provide the "
                    "'filter_set_type' parameter."
                )

        kwargs.setdefault(
            "filters",
            filter_set_type(description="Filters to narrow down results."),
        )
        super().__init__(*args, **kwargs)

    @classmethod
    def resolve_queryset(cls, connection, queryset, info, args):
        queryset: QuerySet = super().resolve_queryset(connection, queryset, info, args)
        if "filters" in args:
            filters: FilterSet = args["filters"]
            return filters.prepare_queryset(queryset).filter(filters.build_query(info))
        else:
            return queryset


class ScalarFilter(graphene.InputObjectType):
    """A stripped-down version of the filterset interfaces that performs operations
    on a single value.
    """

    class Meta:
        abstract = True

    def build_query(self, info: graphene.ResolveInfo, prefix: str) -> Q:
        """Return the Django Q object for this filter.

        :param info: Graphene resolve information.
        :param prefix: String that should be prepended to all lookups. This must be
            given *without* the trailing double underscore (unlike the prefix given
            in the methods in :class:`FilterSet`).
        """
        raise NotImplementedError(
            "subclasses of ScalarFilter must provide a build_query() method"
        )


class NumericFilter(ScalarFilter):
    """Filter for numeric types."""

    value = graphene.Float(
        description="Exact value filter. If this is provided, `minimum` and `maximum` "
        "may not be given."
    )
    minimum = graphene.Float()
    maximum = graphene.Float()

    def build_query(self, info: graphene.ResolveInfo, prefix: str) -> Q:
        if self.value and (self.minimum or self.maximum):
            raise ValidationError(
                "either an exact value filter or a range filter (with minimum and / "
                "or maximum) may be provided, but not both"
            )

        if isinstance(self.value, (int, float)):
            return Q(**{f"{prefix}__exact": self.value})

        query = {}
        if isinstance(self.minimum, (int, float)):
            query[f"{prefix}__gte"] = self.minimum
        if isinstance(self.maximum, (int, float)):
            query[f"{prefix}__lte"] = self.maximum
        return Q(**query)
