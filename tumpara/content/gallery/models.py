from __future__ import annotations

import hashlib
import io
import logging
from fractions import Fraction
from itertools import chain
from math import ceil, sqrt
from typing import BinaryIO, Optional

import PIL.ExifTags
import PIL.Image
import PIL.ImageOps
import pyexiv2
import rawpy
from blurhash import _functions as blurhash_functions
from django.conf import settings
from django.core import validators
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from tumpara.multimedia.models import ImagePreviewable
from tumpara.storage import register_file_handler
from tumpara.storage.models import File, FileHandler, InvalidFileTypeError, Library
from tumpara.timeline.models import (
    ActiveEntryManager,
    Entry,
    EntryManager,
    EntryQuerySet,
)
from tumpara.timeline.util import parse_timestamp_from_filename

__all__ = ["RawPhoto", "Photo", "AutodevelopedPhoto"]
_logger = logging.getLogger(__name__)


# This tuple contains the list of fields that are used to calculate a hash of EXIF data,
# which in turn is used to attribute photos to their raw counterparts, if any. The idea
# here is to use very generic fields that most photo editing / development tools most
# likely won't strip. Ultimately, these are more or less the same ones we read out on
# photos because they are the most popular. If an entry in this list has multiple keys,
# the first one that has a value is used. Further, if a tuple starts with ``True``, it
# is considered non-optional and no digest will be created if it is not present.
METADATA_DIGEST_FIELDS = [
    (
        True,
        "Exif.Image.DateTimeOriginal",
        "Exif.Image.DateTime",
        "Exif.Image.DateTimeDigitized",
    ),
    "Exif.Image.Make",
    "Exif.Image.Model",
    "Exif.Photo.ISOSpeedRatings",
    "Exif.Photo.ExposureTime",
    ("Exif.Photo.FNumber", "Exif.Photo.ApertureValue"),
    "Exif.Photo.FocalLength",
]


def float_or_none(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ZeroDivisionError):
        return None


class BaseImageProcessingMixin(models.Model):
    """Most basic model that does some form of image processing.

    This is the parent for both regular as well as RAW image handlers.

    Note: When overriding :meth:`scan_from_file`, make sure to call ``.save()``.
    """

    file: File

    metadata_digest = models.CharField(
        _("metadata digest value"),
        max_length=64,
        null=True,
        help_text=_("This value is used to map images to their RAW counterparts."),
    )

    class Meta:
        abstract = True

    @classmethod
    def check_raw(cls, library: Library, path: str) -> Optional[bool]:
        """Check if the image at a given path is a raw file.

        This method will return ``True`` if the provided image can be handled by libraw.
        For regular images that should be processed by Pillow, ``False`` will be
        returned. If no image could be loaded, an :exc:`InvalidFileTypeError` will be
        raised.
        """
        try:
            try:
                with library.backend.open(path, "rb") as image_file:
                    result = rawpy.imread(image_file)
                    # Try to find out the raw type. This will make sure the file is
                    # actually scanned by RawPy and not only half-opened.
                    type = result.raw_type
                    return True
            except rawpy.LibRawError:
                try:
                    with library.backend.open(path, "rb") as image_file:
                        return False
                except PIL.UnidentifiedImageError:
                    raise InvalidFileTypeError
        except IOError:
            raise InvalidFileTypeError

    def _open_file(self) -> BinaryIO:
        try:
            file = self.file
            if file is None:
                raise AttributeError
        except AttributeError:
            raise NotImplementedError(
                "Implementations of the image processing mixin must provide a a 'file' "
                "attribute."
            )
        return self.file.open("rb")

    def open_image(self) -> PIL.Image:
        """Open this image as a Pillow ``Image``.

        This should be used for further image processing. It is not guaranteed that
        metadata is present here (it isn't for raw photos).
        """
        return PIL.Image.open(self._open_file())

    def open_metadata(self) -> pyexiv2.ImageMetadata:
        """Open this image as a PyExiv2 metadata object."""
        with self._open_file() as source_file:
            data = source_file.read()
        metadata = pyexiv2.ImageMetadata.from_buffer(data)
        metadata.read()
        return metadata

    def scan_from_file(
        self,
        *,
        metadata: Optional[pyexiv2.ImageMetadata] = None,
        **kwargs,
    ):
        metadata = metadata or self.open_metadata()

        # Calculate the EXIF digest value. This is basically a hash of a bunch of
        # relevant EXIF values.
        hasher = hashlib.blake2b(digest_size=32)
        for keys in METADATA_DIGEST_FIELDS:
            # Parse the keys definition. It has one of the following forms:
            # - "Exif.Image.SomeKey"
            # - ("Exif.Image.SomeKey", "Exif.Image.SomeOtherKey", ...)
            # - (True, "Exif.Image.SomeKey")
            # - (True, "Exif.Image.SomeKey", "Exif.Image.SomeOtherKey", ...)
            # `True` in the first element means that this group is not optional.
            if isinstance(keys, str):
                keys = (keys,)
            if keys[0] is True:
                optional = False
                keys = keys[1:]
            else:
                optional = True

            found = False
            for key in keys:
                value = metadata.get(key, None)
                if value is not None:
                    found = True
                    hasher.update(value.raw_value.encode())
                    break

            if not optional and not found:
                hasher = None
                break

            # Use 0b1 as a kind of separator here.
            hasher.update(bytes(1))
        if hasher is None:
            self.metadata_digest = None
        else:
            self.metadata_digest = hasher.hexdigest()


class BasePhoto(BaseImageProcessingMixin, ImagePreviewable):
    """More complete image processing model that also extracts metadata.

    Note: When overriding :meth:`scan_from_file`, make sure to call ``.save()``.
    """

    format = models.CharField(_("format"), max_length=20)
    width = models.PositiveIntegerField(_("width"))
    height = models.PositiveIntegerField(_("height"))

    camera_make = models.CharField(
        _("camera maker"), max_length=50, null=True, blank=True
    )
    camera_model = models.CharField(
        _("camera model"), max_length=50, null=True, blank=True
    )

    iso_value = models.PositiveIntegerField(_("ISO value"), null=True, blank=True)
    exposure_time = models.FloatField(
        _("exposure time"),
        null=True,
        blank=True,
        validators=(validators.MinValueValidator(0),),
        help_text=_("The shot's exposure time, in seconds."),
    )
    aperture_size = models.FloatField(
        _("aperture size"),
        null=True,
        blank=True,
        validators=(validators.MinValueValidator(0),),
        help_text=_(
            "Aperture / F-Stop value of the shot, in inverse. A value of 4 in this "
            "field implies an f-value of f/4."
        ),
    )
    focal_length = models.FloatField(
        _("focal length"),
        null=True,
        blank=True,
        validators=(validators.MinValueValidator(0),),
        help_text=_("Focal length of the camera, in millimeters."),
    )

    class Meta:
        abstract = True

    @classmethod
    def analyze_file(cls, library: Library, path: str):
        # This model only handles non-raw images.
        if cls.check_raw(library, path) is not False:
            raise InvalidFileTypeError

    @property
    def aspect_ratio(self):
        assert (
            self.width and self.height
        ), "width and height were not available to calculate aspect ratio"
        return self.width / self.height

    @property
    def camera_name(self) -> Optional[str]:
        """The full name of the camera (including make and model)."""
        if not self.camera_model:
            return None
        elif not self.camera_make or self.camera_model.startswith(self.camera_make):
            return self.camera_model
        else:
            return f"{self.camera_make} {self.camera_model}"

    @property
    def exposure_time_fraction(self) -> Optional[Fraction]:
        """Exposure time of the shot, in sections."""
        try:
            return Fraction(self.exposure_time).limit_denominator(10000)
        except TypeError:
            return None

    @property
    def megapixels(self) -> int:
        """Number of megapixels in this photo."""
        return round(self.width * self.height / 1000000)

    def _calculate_blurhash(self, image: PIL.Image.Image):
        self.blurhash = None

        if settings.BLURHASH_SIZE < 1 or settings.BLURHASH_SIZE is None:
            return

        # For the blurhash, make sure that the following is approximately true:
        # - BLURHASH_SIZE = a * b
        # - a / b = width / height
        # This distributes the requested size of the blurhash among the two axis
        # appropriately.
        b = sqrt(settings.BLURHASH_SIZE / image.width * image.height)
        a = b * image.width / image.height
        thumbnail = PIL.ImageOps.exif_transpose(image.convert("RGB"))
        thumbnail.thumbnail(
            (settings.BLURHASH_SIZE * 10, settings.BLURHASH_SIZE * 10),
            PIL.Image.BICUBIC,
        )
        # Here, we re-implement the encode function from the blurhash library so
        # that we can avoid re-opening the image.
        blurhash_result = blurhash_functions.lib.create_hash_from_pixels(
            blurhash_functions.ffi.cast("int", max(0, min(ceil(a), 8))),
            blurhash_functions.ffi.cast("int", max(0, min(ceil(b), 8))),
            blurhash_functions.ffi.cast("int", thumbnail.width),
            blurhash_functions.ffi.cast("int", thumbnail.height),
            blurhash_functions.ffi.new(
                "uint8_t[]",
                list(
                    chain.from_iterable(
                        zip(
                            thumbnail.getdata(band=0),
                            thumbnail.getdata(band=1),
                            thumbnail.getdata(band=2),
                        )
                    )
                ),
            ),
            blurhash_functions.ffi.cast("size_t", thumbnail.width * 3),
        )
        if blurhash_result != blurhash_functions.ffi.NULL:
            self.blurhash = blurhash_functions.ffi.string(blurhash_result).decode()

    def _extract_metadata(self, metadata: pyexiv2.ImageMetadata):
        def extract_value(*keys, cast=None):
            for key in keys:
                try:
                    value = metadata[key].value
                    if cast is not None:
                        value = cast(value)
                    if isinstance(value, str):
                        value = value.strip()
                    return value
                except (KeyError, ValueError):
                    continue
            return None

        self.timestamp = extract_value(
            "Exif.Image.DateTimeOriginal",
            "Exif.Image.DateTime",
            "Exif.Image.DateTimeDigitized",
        )
        if self.timestamp is None:
            self.timestamp = parse_timestamp_from_filename(self.file)

        self.camera_make = extract_value("Exif.Image.Make")
        self.camera_model = extract_value("Exif.Image.Model")
        self.iso_value = extract_value("Exif.Photo.ISOSpeedRatings")
        self.exposure_time = extract_value("Exif.Photo.ExposureTime", cast=float)
        self.aperture_size = extract_value(
            "Exif.Photo.FNumber", "Exif.Photo.ApertureValue", cast=float
        )
        self.focal_length = extract_value("Exif.Photo.FocalLength", cast=float)

        # TODO Extract GPS information.
        self.location = None

    def scan_from_file(
        self,
        *,
        image: Optional[PIL.Image.Image] = None,
        metadata: Optional[pyexiv2.ImageMetadata] = None,
        slow: bool = False,
        **kwargs,
    ):
        image = image or self.open_image()
        metadata = metadata or self.open_metadata()
        super().scan_from_file(image=image, metadata=metadata, slow=slow, **kwargs)

        flip_orientation = 0
        if metadata.get("Exif.Image.Orientation", 1) in (6, 8):
            # The image's 'Orientation' EXIF value may flip width and height
            # information. This is a key that cameras put in when they save the image
            # in a different orientation than it was originally taken in (ex: the
            # image pixels themselves are saved in landscape orientation, like the
            # sensor returns them, but the camera was held upright).
            flip_orientation = 1

        self.format = image.format
        self.width = image.size[flip_orientation]
        self.height = image.size[1 - flip_orientation]

        self._calculate_blurhash(image)
        self._extract_metadata(metadata)

    def render_preview_image(
        self, width: int, height: int, format: str, **kwargs
    ) -> io.BytesIO:
        metadata = self.open_metadata()

        image = self.open_image()
        # Fake the getexif call so that it returns the actual orientation from the
        # loaded metadata (which may come from a raw file, in which case the image we
        # load with .open_image() doesn't have any metadata at all).
        image.getexif = lambda: {0x0112: metadata.get("Exif.Image.Orientation")}

        image = PIL.ImageOps.exif_transpose(image)

        if width in [0, None]:
            width = self.width
        if height in [0, None]:
            height = self.height
        # This creates a thumbnail that has at most the specified size.
        image.thumbnail((width, height), PIL.Image.BICUBIC)

        # For this saving stuff, see https://stackoverflow.com/a/45907694
        buffer = io.BytesIO()
        image.save(fp=buffer, format=format.upper())
        return buffer


class ActiveRawPhotoManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return (
            super()
            .get_queryset()
            .filter(Q(file__isnull=True) | Q(file__orphaned=False))
        )


@register_file_handler(library_context="timeline")
class RawPhoto(BaseImageProcessingMixin, FileHandler):
    """Raw photos are RAW image files that can be developed into actual photos."""

    objects = models.Manager()
    active_objects = ActiveRawPhotoManager()

    class Meta:
        verbose_name = _("raw photo")
        verbose_name_plural = _("raw photos")
        constraints = [
            models.UniqueConstraint(
                fields=("metadata_digest",),
                name="metadata_digest_unique_for_raw_files",
            )
        ]
        default_manager_name = "active_objects"

    @classmethod
    def analyze_file(cls, library: Library, path: str):
        if cls.check_raw(library, path) is not True:
            raise InvalidFileTypeError

    def open_image(self) -> PIL.Image:
        with self.file.open("rb") as image_file:
            raw_image = rawpy.imread(image_file)
        image_data = raw_image.postprocess()
        return PIL.Image.fromarray(image_data)

    def scan_from_file(self, **kwargs):
        super().scan_from_file(**kwargs)
        self.save()

        self.match_renditions()

    def match_renditions(self, **kwargs):
        """Make sure at least one rendition is present.

        Ideally, this means that there is a Photo object which has been matched to this
        raw source. That would either be the camera's JPG output or an edited version of
        the file - depending on the user's workflow. In either case, we don't need to
        automatically develop it. If neither is present, an automatically developed
        version is created and the corresponding AutodevelopedPhoto object will be
        created.

        :param kwargs: Remaining arguments will be passed to the
            :meth:`BasePhoto.scan_from_file` workflow when creating automatic
            renditions.
        """
        # Make sure no outdated renditions are present where the metadata no longer
        # matches this raw file.
        Photo.objects.filter(
            Q(raw_source=self)
            & (~Q(metadata_digest=self.metadata_digest) | ~Q(library=self.file.library))
        ).update(raw_source=None)

        if self.metadata_digest is None:
            # Delete inapplicable autodeveloped renditions.
            AutodevelopedPhoto.objects.filter(raw_source=self).delete()
            return

        # Find photos with the same metadata and match them up.
        user_provided_rendition_count = Photo.active_objects.filter(
            library=self.file.library, metadata_digest=self.metadata_digest
        ).update(raw_source=self)

        if user_provided_rendition_count > 0:
            # Remove the automatically generated rendition because we now have
            # user-provided ones.
            AutodevelopedPhoto.objects.filter(raw_source=self).delete()
        else:
            try:
                auto_rendition = self.auto_rendition
            except AutodevelopedPhoto.DoesNotExist:
                auto_rendition = AutodevelopedPhoto(
                    library_id=self.file.library_id,
                    raw_source=self,
                )
                auto_rendition.scan_from_file(**kwargs)

                # TODO Need to evaluate if 'file' should be None for autodeveloped
                #  photos or refer to the RAW file instead. Probably we want to keep
                #  the raw like it is now so that can be downloaded by the user if
                #  they want to (since the user ideally doesn't know if the photo is
                #  autodeveloped or not).
                auto_rendition.entry_ptr.file = self.file
                auto_rendition.entry_ptr.save()

                self.auto_rendition = auto_rendition


@register_file_handler(library_context="timeline")
class Photo(BasePhoto, Entry, FileHandler):
    """Photos are timeline entries that have been extracted from image files in a
    library."""

    raw_source = models.ForeignKey(
        RawPhoto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renditions",
        related_query_name="rendition",
        verbose_name=_("raw source"),
    )

    class Meta:
        verbose_name = _("photo")
        verbose_name_plural = _("photos")

    def scan_from_file(self, **kwargs):
        super().scan_from_file(**kwargs)

        if self.metadata_digest is not None:
            try:
                # TODO Do we want to limit this filter to objects in the same library?
                self.raw_source = RawPhoto.active_objects.get(
                    file__library=self.library, metadata_digest=self.metadata_digest
                )
            except (RawPhoto.DoesNotExist, RawPhoto.MultipleObjectsReturned):
                self.raw_source = None

        self.save()

        if self.raw_source is not None:
            self.raw_source.match_renditions()


class ActiveAutodevelopedPhotoManager(ActiveEntryManager):
    def get_queryset(self) -> models.QuerySet:
        return EntryManager.get_queryset(self).filter(raw_source__file__orphaned=False)


class AutodevelopedPhoto(BasePhoto, Entry):
    """Autodeveloped photos share the same API with regular photos, but are
    automatically created when no matching photo is found for a RAW file."""

    raw_source = models.OneToOneField(
        RawPhoto,
        on_delete=models.CASCADE,
        related_name="auto_rendition",
        related_query_name="auto_rendition",
        verbose_name=_("raw source"),
    )

    objects = EntryManager()
    active_objects = ActiveAutodevelopedPhotoManager.from_queryset(EntryQuerySet)()

    class Meta:
        verbose_name = _("automatically developed photo")
        verbose_name_plural = _("automatically developed photos")
        constraints = [
            models.UniqueConstraint(
                fields=("raw_source",),
                name="source_unique_for_autodeveloped_photos",
            )
        ]
        default_manager_name = "active_objects"

    @property
    def file(self):
        # This is the magic behind our super secret "raw development" workflow here -
        # we pass through the raw file and let Pillow handle it as it would any other
        # file.
        return self.raw_source.file

    def open_image(self) -> PIL.Image:
        # For the image, we explicitly want the .open_image() method from RawPhoto,
        # because that develops the photo.
        return self.raw_source.open_image()

    def scan_from_file(self, **kwargs):
        super().scan_from_file(**kwargs)

        self.format = "RAW"

        self.save()
