import graphene
from django.core.exceptions import FieldError, ValidationError
from django.db import transaction
from graphene import relay

from tumpara.api.util import resolve_bulk_global_ids, resolve_global_id

from .. import models


class Collection(relay.Node):
    pass


class OrganizeCollection(relay.ClientIDMutation):
    """Add or remove items to / from a collection."""

    class Input:
        collection_id = graphene.ID(
            required=True,
            description="ID of the collection that should be updated.",
        )
        add_item_ids = graphene.List(
            graphene.ID,
            description="List of items (identified by their ID) that should be added "
            "to the collection. The types of these items must be compatible with the "
            "collection.",
        )
        remove_item_ids = graphene.List(
            graphene.ID,
            description="List of items (identified by their ID) that should be "
            "removed from the collection. The types of these items must be compatible "
            "with the collection.",
        )

    collection = graphene.Field(Collection, required=True)

    @classmethod
    @transaction.atomic
    def mutate(
        cls,
        root,
        info: graphene.ResolveInfo,
        input: Input,
    ):
        collection = resolve_global_id(
            input.collection_id,
            info,
            models.Collection,
            Collection,
            check_write_permissions=True,
        )

        applicable_add_ids = {id for id in (input.add_item_ids or []) if id is not None}
        applicable_remove_ids = {
            id for id in (input.remove_item_ids or []) if id is not None
        }
        if len(applicable_add_ids & applicable_remove_ids) > 0:
            raise ValueError("Received one or more IDs for both adding and removing.")

        for _, primary_keys in resolve_bulk_global_ids(applicable_add_ids, info):
            try:
                collection.items.add(*primary_keys)
            except (FieldError, ValidationError):
                raise TypeError(
                    f"Failed adding an item to the collection. Perhaps it does "
                    f"not have the correct type?"
                )

        for _, primary_keys in resolve_bulk_global_ids(applicable_remove_ids, info):
            try:
                collection.items.remove(*primary_keys)
            except (FieldError, ValidationError):
                raise TypeError(
                    f"Failed to delete an item from the collection. Perhaps "
                    f"it does not have the correct type?"
                )

        collection.save()
        return {"collection": collection}
