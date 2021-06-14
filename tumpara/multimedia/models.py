import io

from django.db import models
from django.utils.translation import gettext_lazy as _


class ImagePreviewable(models.Model):
    """Base class for objects where a single still image can be rendered as a
    preview. This is mostly applicable for thumbnails.
    """

    blurhash = models.CharField(
        "blurhash",
        max_length=100,
        null=True,
        help_text=_(
            "Blurhash textual representation that can be used for loading placeholders."
        ),
    )

    class Meta:
        abstract = True

    def render_preview_image(
        self, width: int, height: int, format: str, **kwargs
    ) -> io.BytesIO:
        """Render a preview / thumbnail of this object.

        The resulting image should target the specified dimensions. Smaller results
        are okay, but it may not exceed them on either axis.

        :param width: The desired thumbnail width.
        :param height: The desired thumbnail height.
        :param format: The desired image format.
        """
        raise NotImplementedError
