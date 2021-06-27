import graphene
from django.db.models import QuerySet
from graphene_django import DjangoObjectType

from tumpara.api.util import convert_model_field
from tumpara.storage.api import LibraryContent

from .. import models


class TimelineEntryInterface(LibraryContent):
    timestamp = convert_model_field(models.Entry, "timestamp")
    location = convert_model_field(models.Entry, "location")
    created_at = convert_model_field(models.Entry, "created_at")
    stack_size = graphene.Int(
        required=True, description="Number of items in this entry's stack."
    )
    stack_representative = convert_model_field(models.Entry, "stack_representative")

    class Meta:
        name = "TimelineEntry"


class BaseTimelineEntry(DjangoObjectType):
    class Meta:
        abstract = True

    @classmethod
    def get_queryset(cls, queryset: QuerySet, info: graphene.ResolveInfo) -> QuerySet:
        assert issubclass(cls._meta.model, models.Entry)
        return cls._meta.model.objects.for_user(info.context.user, queryset=queryset)

    @classmethod
    def get_node(cls, info: graphene.ResolveInfo, id):
        try:
            entry: models.Entry = cls._meta.model.objects.get(pk=id)
        except cls._meta.model.DoesNotExist:
            return None

        # If the entry is visible for a given user, we can directly return it.
        if entry.check_visibility(info.context.user):
            return entry

        # If it is not visible, they may still be allowed to access it if it is in
        # one of their collections.
        collection_items = models.AlbumItem.objects.filter(
            collection__in=models.Album.objects.for_user(info.context.user), entry=entry
        )
        if collection_items.count() > 0:
            return entry

        return None
