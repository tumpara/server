import graphene
from django.db.models import F, Q, QuerySet
from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.api import Subschema
from tumpara.api.filtering import FilterSet
from tumpara.storage.api import LibraryContent
from tumpara.timeline.api import TimelineEntryInterface
from tumpara.timeline.api.entry_filtersets import entry_type_filterset

from . import models


class FooEntry(DjangoObjectType):
    class Meta:
        name = "TestTimelineFooEntry"
        model = models.FooEntry
        interfaces = (relay.Node, TimelineEntryInterface, LibraryContent)

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        return models.FooEntry.objects.for_user(
            info.context.user, queryset=queryset, writing=True
        )


class BarEntry(DjangoObjectType):
    class Meta:
        name = "TestTimelineBarEntry"
        model = models.BarEntry
        interfaces = (relay.Node, TimelineEntryInterface, LibraryContent)

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        return models.BarEntry.objects.for_user(
            info.context.user, queryset=queryset, writing=True
        )


@entry_type_filterset("FooEntry", "fooentry")
class FooEntryFilterSet(FilterSet):
    contains_alpha = graphene.Boolean()

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        if self.contains_alpha:
            return Q(**{f"{prefix}the_string__regex": r"[a-zA-Z]"})
        else:
            return Q()


@entry_type_filterset("BarEntry", "barentry")
class BarEntryFilterSet(FilterSet):
    large = graphene.Boolean()
    product_positive = graphene.Boolean()

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        result = Q()
        if self.large:
            result &= Q(**{f"{prefix}first_number__gt": 50})
        if self.product_positive:
            result &= Q(**{f"{prefix}product__gt": 0})
        return result

    def prepare_queryset(self, queryset: QuerySet, prefix: str = "") -> QuerySet:
        if self.product_positive:
            queryset = queryset.annotate(
                barentry__product=F(f"{prefix}first_number")
                * F(f"{prefix}second_number")
            )
        return queryset


subschema = Subschema(types=[FooEntry, BarEntry])
