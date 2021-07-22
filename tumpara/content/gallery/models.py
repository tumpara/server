from __future__ import annotations

import hashlib
import io
import logging
import pickle
from datetime import datetime
from fractions import Fraction
from itertools import chain
from math import ceil, sqrt
from typing import Optional

import PIL.ExifTags
import PIL.Image
import PIL.ImageOps
import rawpy
from blurhash import _functions as blurhash_functions
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core import validators
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

import tumpara.timeline.util
from tumpara.multimedia.models import ImagePreviewable
from tumpara.storage import register_file_handler
from tumpara.storage.models import File, FileHandler, InvalidFileTypeError, Library
from tumpara.timeline.models import (
    ActiveEntryManager,
    Entry,
    EntryManager,
    EntryQuerySet,
)

from .util import degrees_to_decimal

__all__ = ["RawPhoto", "Photo", "AutodevelopedPhoto"]
_logger = logging.getLogger(__name__)


# This tuple contains the list of fields that are used to calculate a hash of EXIF data,
# which in turn is used to attribute photos to their raw counterparts, if any. The idea
# here is to use very generic fields that most photo editing / development tools most
# likely won't strip. Ultimately, these are more or less the same ones we read out on
# photos because they are the most popular. Each field also has a boolean that
# determines whether it's optional - when a non-optional field doesn't exit, no hash
# is generated.
METADATA_DIGEST_FIELDS = (
    (0x9003, True),  # DateTimeOriginal
    (0x010F, False),  # Make
    (0x0110, False),  # Model
    (0x8827, False),  # ISOSpeedRatings
    (0x829A, False),  # ExposureTime
    (0x829D, False),  # FNumber
    (0x9202, False),  # ApertureValue
    (0x920A, False),  # FocalLength
)


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
    def open_image(cls, library: Library, path: str):
        try:
            try:
                with library.backend.open(path, "rb") as image_file:
                    result = rawpy.imread(image_file)
                    # Try to find out the raw type. This will make sure the file is
                    # scanned.
                    type = result.raw_type
                    return result
            except rawpy.LibRawError:
                try:
                    with library.backend.open(path, "rb") as image_file:
                        return PIL.Image.open(image_file)
                except PIL.UnidentifiedImageError:
                    raise InvalidFileTypeError
        except IOError:
            raise InvalidFileTypeError

    @property
    def pil_image(self) -> PIL.Image:
        """Open this image as a Pillow :class:`PIL.Image`."""
        try:
            file = self.file
            if file is None:
                raise AttributeError
        except AttributeError:
            raise NotImplementedError(
                "Implementations of the image processing mixin must provide a a 'file' "
                "attribute."
            )
        return PIL.Image.open(self.file.open("rb"))

    def scan_from_file(
        self,
        *,
        pil_image: Optional[PIL.Image.Image] = None,
        **kwargs,
    ):
        image = pil_image or self.pil_image

        exif = image.getexif()
        # Unflatten IFD values, just as in get_exif_tags().
        exif = exif.get_ifd(0x8769) | dict(exif)

        # Calculate the EXIF digest value. This is basically a hash of a bunch of
        # relevant EXIF values.
        hasher = hashlib.blake2b(digest_size=32)
        for key, optional in METADATA_DIGEST_FIELDS:
            if key not in exif or exif[key] is None:
                if optional:
                    hasher.update(bytes(1))
                else:
                    hasher = None
                    break
            else:
                # We use pickle to dump a bytes representation of the EXIF value here.
                # Normally, this could be a security concern but because we will never
                # unpickle this again we can get away with it here.
                hasher.update(pickle.dumps(exif[key]))
        if hasher is None:
            self.metadata_digest = None
        else:
            self.metadata_digest = hasher.hexdigest()

    def get_exif_tags(self, *, pil_image: Optional[PIL.Image.Image] = None) -> dict:
        """Extract EXIF tags with their human-readable names.

        :param pil_image: Pre-opened :class:`PIL.Image` instance, used to limit disk
            access.
        :return: A dictionary of extracted infos."""
        image = pil_image or self.pil_image
        exif = image.getexif()

        result = {}

        def add_item(key, value):
            pretty_key = PIL.ExifTags.TAGS[key] if key in PIL.ExifTags.TAGS else key
            result[pretty_key] = value

        for key, value in exif.items():
            add_item(key, value)

        # Unflatten IFD values, see here:
        # https://github.com/python-pillow/Pillow/pull/4947
        # If we don't do this a bunch of tags are dropped.
        ifd = exif.get_ifd(0x8769)
        for key, value in ifd.items():
            add_item(key, value)

        if "GPSInfo" in result and isinstance(result["GPSInfo"], int):
            del result["GPSInfo"]
        if "GPSInfo" in result:
            gps_info = {}
            for key, value in result["GPSInfo"].items():
                pretty_key = (
                    PIL.ExifTags.GPSTAGS[key] if key in PIL.ExifTags.GPSTAGS else key
                )
                gps_info[pretty_key] = value
            result["GPSInfo"] = gps_info

        return result


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
        image = cls.open_image(library, path)
        if not isinstance(image, PIL.Image.Image):
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

    def _extract_metadata(self, image: PIL.Image.Image):
        exif = self.get_exif_tags(pil_image=image)

        for key in (
            "camera_make",
            "camera_model",
            "iso_value",
            "exposure_time",
            "aperture_size",
            "focal_length",
            "location",
        ):
            setattr(self, key, None)

        timestamp = None
        for tag in ["DateTimeOriginal", "DateTime", "DateTimeDigitized"]:
            try:
                timestamp = datetime.strptime(exif[tag], "%Y:%m:%d %H:%M:%S")
                break
            except (KeyError, ValueError):
                continue
        if timestamp is None:
            timestamp = tumpara.timeline.util.parse_timestamp_from_filename(self.file)
        self.timestamp = timestamp

        if "Make" in exif:
            self.camera_make = exif["Make"].strip()

        if "Model" in exif:
            self.camera_model = exif["Model"].strip()

        if "ISOSpeedRatings" in exif:
            self.iso_value = exif["ISOSpeedRatings"]

        if "ExposureTime" in exif:
            value = exif["ExposureTime"]
            self.exposure_time = float_or_none(value)

        if "FNumber" in exif:
            value = exif["FNumber"]
            self.aperture_size = float_or_none(value)
        elif "ApertureValue" in exif:
            value = exif["ApertureValue"]
            self.aperture_size = float_or_none(value)

        if "FocalLength" in exif:
            value = exif["FocalLength"]
            self.focal_length = float_or_none(value)

        if "GPSInfo" in exif:
            gps_info = exif["GPSInfo"]
            try:
                latitude = degrees_to_decimal(
                    gps_info["GPSLatitude"], gps_info["GPSLatitudeRef"]
                )
                longitude = degrees_to_decimal(
                    gps_info["GPSLongitude"], gps_info["GPSLongitudeRef"]
                )
                self.location = Point(latitude, longitude)
            except (ValueError, KeyError):
                pass

    def scan_from_file(
        self,
        *,
        pil_image: Optional[PIL.Image.Image] = None,
        slow: bool = False,
        **kwargs,
    ):
        image = pil_image or self.pil_image
        super().scan_from_file(pil_image=image, slow=slow, **kwargs)

        exif = image.getexif()
        flip_orientation = 0
        if exif and 274 in exif:
            # The image's 'Orientation' EXIF value may flip width and height
            # information. This is a key that cameras put in when they save the image
            # in a different orientation than it was originally taken in (ex: the
            # image pixels themselves are saved in landscape orientation, like the
            # sensor returns them, but the camera was held upright).
            if exif[274] in [6, 8]:
                flip_orientation = 1

        self.format = image.format
        self.width = image.size[flip_orientation]
        self.height = image.size[1 - flip_orientation]

        self._calculate_blurhash(image)
        self._extract_metadata(image)

    def render_preview_image(
        self, width: int, height: int, format: str, **kwargs
    ) -> io.BytesIO:
        image = PIL.ImageOps.exif_transpose(self.pil_image)

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

    @classmethod
    def analyze_file(cls, library: Library, path: str):
        image = cls.open_image(library, path)
        if not isinstance(image, rawpy.RawPy):
            raise InvalidFileTypeError

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
            :meth:`BasePhoto.scan_from_file` workflow.
        """
        if self.metadata_digest is None:
            return

        # Make sure no outdated renditions are present where the metadata no longer
        # matches this raw file.
        Photo.objects.filter(
            Q(raw_source=self)
            & (~Q(metadata_digest=self.metadata_digest) | ~Q(library=self.file.library))
        ).update(raw_source=None)

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

    @property
    def file(self):
        # This is the magic behind our super secret "raw development" workflow here -
        # we pass through the raw file and let Pillow handle it as it would any other
        # file.
        # TODO In the future, we should probably process this with some library that's
        #   actually built for developing RAW images. Then we would take that output and
        #   return it as a file-like object here so it is processed by the methods in
        #   BasePhoto as a regular JPG. Not sure what Pillow uses under the hood for
        #   rendering RAW files, so some test would be needed to find out if the
        #   resulting images are actually better that straight up using Pillow.
        return self.raw_source.file

    def scan_from_file(self, **kwargs):
        super().scan_from_file(**kwargs)

        self.format = "RAW"

        self.save()
