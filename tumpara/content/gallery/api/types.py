from typing import Optional, Tuple

import graphene
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
        model = models.Photo
        interfaces = (
            relay.Node,
            TimelineEntryInterface,
            Archivable,
            LibraryContent,
            FileHandler,
            ImagePreviewable,
        )
        exclude = ("entry_ptr",)

    @staticmethod
    def resolve_exposure_time_fraction(
        parent: models.Photo, info: graphene.ResolveInfo
    ) -> Optional[Tuple[int, int]]:
        result = parent.exposure_time_fraction
        return (result.numerator, result.denominator) if result is not None else None
