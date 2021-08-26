import graphene
from django.db import transaction
from graphene import relay

from tumpara.api.util import resolve_bulk_global_ids, resolve_global_id

from .. import models
from .timeline_view import TimelineEntryInterface


class StackTimelineEntries(relay.ClientIDMutation):
    """Stack a set of timeline entries together."""

    class Input:
        ids = graphene.List(
            graphene.ID,
            description="List of entries (identified by their node ID) to stack "
            "together. The first item in this list will become the representative.",
        )

    entries = graphene.List(
        TimelineEntryInterface,
        required=True,
        description="The set of all updated nodes.",
    )

    @classmethod
    @transaction.atomic
    def mutate(cls, root, info: graphene.ResolveInfo, input: Input):
        primary_keys = []
        for _, model_primary_keys in resolve_bulk_global_ids(
            input.ids,
            info,
            models.Entry,
            TimelineEntryInterface,
            check_write_permissions=True,
        ):
            primary_keys.extend(model_primary_keys)

        models.Entry.objects.stack(primary_keys, requester=info.context.user)

        return {
            "entries": (
                resolve_global_id(
                    given_id,
                    info,
                    models.Entry,
                    TimelineEntryInterface,
                )
                for given_id in input.ids
            )
        }


class UnstackTimelineEntry(relay.ClientIDMutation):
    """Remove a timeline entry from it's stack."""

    class Input:
        id = graphene.ID(required=True, description="ID of the entry to unstack.")
        clear = graphene.Boolean(
            default_value=False,
            description="Set this to true to clear the entire stack, removing all "
            "entries from it. Afterwards, every entry that was in the stack before "
            "will be unstacked. By default, only the provided entry is removed from "
            "the stack and other entries are left untouched.",
        )

    entries = graphene.List(
        TimelineEntryInterface,
        required=True,
        description="List of all entries that were in the stack. Note that this list "
        "also item that have been removed as a result of this mutation.",
    )

    @classmethod
    @transaction.atomic
    def mutate(cls, root, info, input: Input):
        entry = resolve_global_id(
            input.id,
            info,
            models.Entry,
            TimelineEntryInterface,
            check_write_permissions=True,
        )

        if entry.stack_key is None:
            return {"entries": []}

        stack_pks = [
            obj["pk"]
            for obj in models.Entry.active_objects.for_user(info.context.user)
            .filter(stack_key=entry.stack_key)
            .values("pk")
        ]

        if input.clear:
            entry.clear_stack(requester=info.context.user)
        else:
            entry.unstack(requester=info.context.user)

        stack_entries = models.Entry.active_objects.filter(pk__in=stack_pks)
        return {
            "entries": models.Entry.objects.with_stack_size(
                info.context.user, stack_entries
            )
        }
