import graphene
from django.db.models import F, Q, QuerySet

from tumpara.api import Subschema
from tumpara.storage.api import LibraryContentFilterSet, LibraryContentObjectType
from tumpara.timeline.api import TimelineEntryInterface
from tumpara.timeline.api.entry_filtersets import entry_type_filterset

from . import models


class FooEntry(LibraryContentObjectType):
    class Meta:
        name = "TestTimelineFooEntry"
        model = models.FooEntry
        interfaces = (TimelineEntryInterface,)


class BarEntry(LibraryContentObjectType):
    class Meta:
        name = "TestTimelineBarEntry"
        model = models.BarEntry
        interfaces = (TimelineEntryInterface,)


@entry_type_filterset("FooEntry", "fooentry")
class FooEntryFilterSet(LibraryContentFilterSet):
    contains_alpha = graphene.Boolean()

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        query = super().build_query(info, prefix)

        if self.contains_alpha:
            query &= Q(**{f"{prefix}the_string__regex": r"[a-zA-Z]"})

        return query


@entry_type_filterset("BarEntry", "barentry")
class BarEntryFilterSet(LibraryContentFilterSet):
    large = graphene.Boolean()
    product_positive = graphene.Boolean()

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        query = super().build_query(info, prefix)

        if self.large:
            query &= Q(**{f"{prefix}first_number__gt": 50})
        if self.product_positive:
            query &= Q(**{f"{prefix}product__gt": 0})

        return query

    def prepare_queryset(self, queryset: QuerySet, prefix: str = "") -> QuerySet:
        queryset = super().prepare_queryset(queryset, prefix)

        if self.product_positive:
            queryset = queryset.annotate(
                barentry__product=F(f"{prefix}first_number")
                * F(f"{prefix}second_number")
            )

        return queryset


subschema = Subschema(types=[FooEntry, BarEntry])
