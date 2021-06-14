import itertools

import graphene
from django.db import transaction
from django.db.models import Q
from graphene import relay

from tumpara.api.filtering import FilterSet
from tumpara.api.util import convert_model_field, resolve_bulk_global_ids

from .. import models


class Archivable(relay.Node):
    archived = convert_model_field(models.Archivable, "archived")


class ArchivableFilterSet(FilterSet):
    include_archived = graphene.Boolean(
        default_value=False,
        description="Include archived items, which are not returned by default.",
    )
    only_archived = graphene.Boolean(
        default_value=False,
        description="Only return archived items. This cannot be used together with "
        "`includeArchived`.",
    )

    class Meta:
        abstract = True

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        # Make sure at most one of the archive-related queries are set.
        if {self.only_archived, self.include_archived} == {True}:
            raise ValueError(
                "At most one of include_archived and only_archived may be used."
            )

        query = Q()

        if self.only_archived:
            query &= Q(**{f"{prefix}archived": True})
        elif not self.include_archived:
            query &= Q(**{f"{prefix}archived": False})

        return query


class OrganizeArchive(relay.ClientIDMutation):
    """Set or unset item(s) archived status."""

    class Input:
        archive_ids = graphene.List(
            graphene.ID,
            description="List of item IDs that should be marked archived. These must "
            "be Archivable types.",
        )
        unarchive_ids = graphene.List(
            graphene.ID,
            description="List of item IDs that should no longer be archived. These "
            "must be Archivable types.",
        )

    affected_items = graphene.List(
        Archivable,
        description="List of all targeted objects. Items will still be listed here if "
        "their archived state did not change as a result of this operation.",
    )

    @classmethod
    @transaction.atomic
    def mutate(cls, root, info: graphene.ResolveInfo, input: Input):
        applicable_archive_ids = {
            id for id in (input.archive_ids or []) if id is not None
        }
        applicable_unarchive_ids = {
            id for id in (input.unarchive_ids or []) if id is not None
        }
        if len(applicable_archive_ids & applicable_unarchive_ids) > 0:
            raise ValueError(
                "Received one or more IDs for both archiving and unarchiving."
            )

        affected_querysets = []

        def run(id_set, value):
            for model, primary_keys in resolve_bulk_global_ids(
                id_set,
                info,
                models.Archivable,
                Archivable,
                check_write_permissions=True,
            ):
                queryset = model.objects.filter(pk__in=primary_keys)
                queryset.update(archived=value)
                affected_querysets.append(queryset)

        run(applicable_archive_ids, True)
        run(applicable_unarchive_ids, False)

        return {"affected_items": itertools.chain(*affected_querysets)}
