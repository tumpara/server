import graphene
from django.db.models import F, Q, QuerySet, functions

from tumpara.api.filtering import *
from tumpara.timeline.api.entry_filtersets import entry_type_filterset


@entry_type_filterset("Photo", ("photo", "autodevelopedphoto"))
class PhotoFilterSet(FilterSet):
    width = graphene.Field(NumericFilter)
    height = graphene.Field(NumericFilter)
    smaller_axis = graphene.Field(
        NumericFilter, description="The smaller value of `width` and `height`."
    )
    larger_axis = graphene.Field(
        NumericFilter, description="The larger value of `width` and `height`."
    )
    megapixels = graphene.Field(NumericFilter)

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        query = super().build_query(info, prefix)

        for filter_name in [
            "width",
            "height",
            "smaller_axis",
            "larger_axis",
            "megapixels",
        ]:
            try:
                query &= getattr(self, filter_name).build_query(
                    info,
                    # No need to add the trailing '__' to ScalarFilter objects.
                    prefix + filter_name,
                )
            except AttributeError:
                pass

        return query

    def prepare_queryset(self, queryset: QuerySet, prefix: str = "") -> QuerySet:
        queryset = super().prepare_queryset(queryset, prefix)

        if self.megapixels:
            queryset = queryset.annotate(
                **{
                    f"{prefix}megapixels": functions.Round(
                        F(f"{prefix}width") * F(f"{prefix}height") / 1000000.0
                    )
                }
            )
        if self.smaller_axis:
            queryset = queryset.annotate(
                **{
                    f"{prefix}smaller_axis": functions.Least(
                        f"{prefix}width", f"{prefix}height"
                    )
                }
            )
        if self.larger_axis:
            queryset = queryset.annotate(
                **{
                    f"{prefix}larger_axis": functions.Greatest(
                        f"{prefix}width", f"{prefix}height"
                    )
                }
            )

        return queryset
