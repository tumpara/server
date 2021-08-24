from typing import Optional

import graphene
from django.db.models import Q, QuerySet
from graphene import relay

from tumpara.collections.api import Archivable
from tumpara.multimedia.api import ImagePreviewable
from tumpara.storage.api import FileHandler, LibraryContent
from tumpara.timeline.api import BaseTimelineEntry, TimelineEntryInterface

from .. import models


class Photo(BaseTimelineEntry):
    megapixels = graphene.Int(
        required=True, description=models.Photo.megapixels.__doc__
    )
    camera_name = graphene.String(description=models.Photo.camera_name.__doc__)
    exposure_time_fraction = graphene.List(
        graphene.NonNull(graphene.Int),
        description=models.Photo.exposure_time_fraction.__doc__,
    )

    class Meta:
        model = models.BasePhoto
        interfaces = (
            relay.Node,
            TimelineEntryInterface,
            Archivable,
            LibraryContent,
            FileHandler,
            ImagePreviewable,
        )
        exclude = ("entry_ptr",)

    @classmethod
    def get_base_queryset(cls):
        # This is used by _resolve_schema_type_queryset in util.py and is required
        # because the model we have here is abstract.
        return models.Entry.active_objects.get_queryset()

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        # Need to override this because the superclass uses the manager from
        # cls._meta.model which is not present in BasePhoto (because it's abstract).
        return models.Entry.active_objects.for_user(
            info.context.user, queryset=queryset, writing=writing
        ).filter(Q(photo__isnull=False) | Q(autodevelopedphoto__isnull=False))

    # The following method is overridden here because DjangoObjectType only checks for
    # exact type matches, but this API type here is for both regular and autodeveloped
    # photos. We don't want to use two API types because then clients have to needlessly
    # differ between them.
    @classmethod
    def is_type_of(cls, root, info):
        if super().is_type_of(root, info):
            return True

        if cls._meta.model._meta.proxy:
            model = root._meta.model
        else:
            model = root._meta.model._meta.concrete_model

        return model in (
            models.Photo,
            models.AutodevelopedPhoto,
        )

    @staticmethod
    def resolve_exposure_time_fraction(
        parent: models.Photo, info: graphene.ResolveInfo
    ) -> Optional[tuple[int, int]]:
        result = parent.exposure_time_fraction
        return (result.numerator, result.denominator) if result is not None else None
