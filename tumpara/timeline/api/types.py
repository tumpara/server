from typing import Optional

import graphene
from django.core.exceptions import ObjectDoesNotExist
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
    def get_queryset(
        cls, queryset: Optional[QuerySet], info: graphene.ResolveInfo
    ) -> QuerySet:
        assert issubclass(cls._meta.model, models.Entry)
        return cls._meta.model.active_objects.for_user(
            info.context.user, queryset=queryset
        )

    @classmethod
    def get_node(cls, info: graphene.ResolveInfo, id):
        try:
            return cls.get_queryset(None, info).get(pk=id).implementation
        # We cant use cls._meta.model.DoesNotExist here because the model may be
        # abstract (for example BasePhoto isn't).
        except ObjectDoesNotExist:
            pass

        # If it is not visible, they may still be allowed to access it if it is in
        # one of their collections.
        try:
            return models.AlbumItem.objects.get(
                collection__in=models.Album.objects.for_user(info.context.user),
                entry__pk=id,
            ).entry.implementation
        except models.AlbumItem.DoesNotExist:
            return None
