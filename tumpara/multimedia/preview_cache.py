from __future__ import annotations

import os.path
import shutil
from dataclasses import dataclass

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from .models import ImagePreviewable


@dataclass
class PreviewCacheKey:
    app_label: str
    model_name: str
    pk: str

    @staticmethod
    def from_obj(obj: Model) -> PreviewCacheKey:
        if not isinstance(obj, Model):
            raise TypeError("Cannot create preview cache keys from non-Django models.")
        return PreviewCacheKey(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            pk=str(obj.pk),
        )

    @staticmethod
    def from_json(array) -> PreviewCacheKey:
        if not len(array) == 3:
            raise TypeError(
                "Deserializing preview cache keys requires iterables with three elements."
            )
        return PreviewCacheKey(*array)

    def to_json(self) -> tuple:
        return self.app_label, self.model_name, self.pk


def get_preview_path(key: PreviewCacheKey, type, filename):
    return os.path.join(
        settings.PREVIEW_ROOT,
        f"{key.app_label}:{key.model_name}",
        (key.pk + "---")[:3],
        key.pk,
        f"{type}-{filename}",
    )


def clean_previews(key: PreviewCacheKey):
    """Clean all previews in the cache for a given model."""
    shutil.rmtree(
        os.path.join(
            settings.PREVIEW_ROOT,
            f"{key.app_label}:{key.model_name}",
            (key.pk + "---")[:3],
            key.pk,
        ),
        ignore_errors=True,
    )


def place_image_preview(key, width, height, format) -> str:
    """Make sure a given image preview is present in the cache.

    If the file is not yet available, it will be rendered.

    :returns: The path of the preview file.

    :raises django.core.exceptions.DoesNotExist: When the key does not describe a valid
        object.
    """
    preview_path = get_preview_path(key, "image", f"{width}x{height}.{format}")

    if not os.path.isfile(preview_path):
        content_type: ContentType = ContentType.objects.get_by_natural_key(
            key.app_label, key.model_name
        )
        obj: ImagePreviewable = content_type.get_object_for_this_type(pk=key.pk)

        os.makedirs(os.path.dirname(preview_path), exist_ok=True)

        preview = obj.render_preview_image(width, height, format)
        with open(preview_path, "wb") as file:
            file.write(preview.getbuffer())

    return preview_path
