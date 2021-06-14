import graphene
from django.core.exceptions import ValidationError
from django.db.models import Q

from tumpara.api.filtering import ScalarFilter
from tumpara.api.util import resolve_bulk_global_ids


class CollectionsFilter(ScalarFilter):
    """Filter for collection entries."""

    include = graphene.List(
        graphene.ID,
        description="Collections that should contain the object. Any items that are "
        "in at least one of the specified collections will match.",
    )
    exclude = graphene.List(
        graphene.ID,
        description="Collections that must not contain the object. If an item is in "
        "any one of these collections, it will not match.",
    )

    def build_query(
        self, info: graphene.ResolveInfo, prefix: str, collection_model, collection_type
    ) -> Q:
        include_pks = set()
        for _, primary_keys in resolve_bulk_global_ids(
            (id for id in (self.include or []) if id is not None),
            info,
            collection_model,
            collection_type,
        ):
            include_pks.update(primary_keys)

        exclude_pks = set()
        for _, primary_keys in resolve_bulk_global_ids(
            (id for id in (self.exclude or []) if id is not None),
            info,
            collection_model,
            collection_type,
        ):
            exclude_pks.update(primary_keys)

        if len(include_pks & exclude_pks) > 0:
            raise ValidationError(
                "Cannot filter for items both inside and not inside any one "
                "collection. The IDs in 'include' and 'exclude' may not overlap."
            )

        result = Q()

        if len(include_pks) > 0:
            result &= Q(**{f"{prefix}__pk__in": include_pks})

        if len(exclude_pks) > 0:
            result &= ~Q(**{f"{prefix}__pk__in": exclude_pks})

        return result
