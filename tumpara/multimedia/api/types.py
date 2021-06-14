import graphene
from django.core import signing
from django.urls import reverse as reverse_url

from .. import models
from ..preview_cache import PreviewCacheKey


class ImagePreviewable(graphene.Interface):
    """Objects of this type expose an API for generating preview / thumbnail images."""

    blurhash = graphene.String(
        description="A textual representation of the image which clients can use to "
        "display an appropriately colored blob while loading the actual resource. See"
        "https://blurha.sh/ for details."
    )

    image_preview_url = graphene.String(
        description="URL under which a preview is available. The link returned here "
        "will be valid for one hour.",
        width=graphene.Int(
            required=True, description="Maximum width the returned preview should have."
        ),
        height=graphene.Int(
            required=True,
            description="Maximum height the returned preview should have.",
        ),
        format=graphene.String(
            default_value="webp",
            description="The desired image format. Choices are `jpeg` and `webp`, the "
            "latter being the default.",
        ),
    )

    @staticmethod
    def resolve_image_preview_url(
        obj: models.ImagePreviewable,
        info: graphene.ResolveInfo,
        width: int,
        height: int,
        format: str,
    ):
        # Build a description object and sign it, see the `preview_image` for details.
        description = (
            PreviewCacheKey.from_obj(obj).to_json(),
            width,
            height,
            format,
        )
        signed_description = signing.dumps(description, compress=True)
        return reverse_url("multimedia_preview_image", args=(signed_description,))
