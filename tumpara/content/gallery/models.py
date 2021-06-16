from __future__ import annotations

import io
import logging
from datetime import datetime
from fractions import Fraction
from itertools import chain
from math import ceil, sqrt
from typing import Optional

import PIL.ExifTags
import PIL.Image
from blurhash import _functions as blurhash_functions
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core import validators
from django.db import models
from django.utils.translation import gettext_lazy as _

import tumpara.timeline.util
from tumpara.multimedia.models import ImagePreviewable
from tumpara.storage import register_file_handler
from tumpara.storage.models import FileHandler, InvalidFileTypeError, Library
from tumpara.timeline.models import Entry

from .util import correct_pil_image_orientation, degrees_to_decimal

__all__ = ["Photo"]
_logger = logging.getLogger(__name__)


class ImageFileHandler(FileHandler, ImagePreviewable):
    """Base class for file handlers that deal with images."""

    format = models.CharField(_("format"), max_length=20)
    width = models.PositiveIntegerField(_("width"))
    height = models.PositiveIntegerField(_("height"))

    class Meta:
        abstract = True

    @property
    def aspect_ratio(self):
        assert (
            self.width and self.height
        ), "width and height were not available to calculate aspect ratio"
        return self.width / self.height

    @property
    def pil_image(self) -> PIL.Image:
        """Open this image as a Pillow :class:`PIL.Image`."""
        return PIL.Image.open(self.file.open("rb"))

    @classmethod
    def analyze_file(cls, library: Library, path: str):
        try:
            PIL.Image.open(library.backend.open(path, "rb"))
        except (PIL.UnidentifiedImageError, IOError):
            raise InvalidFileTypeError

    def scan_from_file(
        self,
        *,
        pil_image: Optional[PIL.Image.Image] = None,
        slow: bool = False,
        **kwargs,
    ):
        image = pil_image or self.pil_image

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

        if settings.BLURHASH_SIZE and settings.BLURHASH_SIZE > 1:
            # For the blurhash, make sure that the following is approximately true:
            # - BLURHASH_SIZE = a * b
            # - a / b = width / height
            # This distributes the requested size of the blurhash among the two axis
            # appropriately.
            b = sqrt(settings.BLURHASH_SIZE / image.width * image.height)
            a = b * image.width / image.height
            thumbnail = correct_pil_image_orientation(image.convert("RGB"))
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

    def get_exif_tags(self, *, pil_image: Optional[PIL.Image.Image] = None) -> dict:
        """Extract EXIF tags with their human-readable names.

        :param pil_image: Pre-opened :class:`PIL.Image` instance, used to limit disk
            access.
        :return: A dictionary of extracted infos."""
        pil_image = pil_image or self.pil_image
        exif = pil_image.getexif()

        result = {}

        def add_item(key, value):
            pretty_key = PIL.ExifTags.TAGS[key] if key in PIL.ExifTags.TAGS else key
            result[pretty_key] = value

        for key, value in exif.items():
            add_item(key, value)

        # Unflatten IFD values, see here:
        # https://github.com/python-pillow/Pillow/pull/4947
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

    def render_preview_image(
        self, width: int, height: int, format: str, **kwargs
    ) -> io.BytesIO:
        image = correct_pil_image_orientation(self.pil_image)

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


@register_file_handler(library_context="timeline")
class Photo(Entry, ImageFileHandler):
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
        verbose_name = _("photo")
        verbose_name_plural = _("photos")

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
    def exposure_time_fraction(self) -> Fraction:
        """Exposure time of the shot, in sections."""
        try:
            return Fraction(self.exposure_time).limit_denominator(10000)
        except TypeError:
            return None

    @property
    def megapixels(self) -> int:
        """Number of megapixels in this photo."""
        return round(self.width * self.height / 1000000)

    def scan_from_file(
        self,
        *,
        pil_image: Optional[PIL.Image.Image] = None,
        **kwargs,
    ):
        """Extract EXIF metadata from the source.

        :param pil_image: Pre-opened :class:`PIL.Image` instance, used to limit disk
            access.
        """
        image = pil_image or self.pil_image
        super().scan_from_file(**kwargs, pil_image=pil_image)
        exif = self.get_exif_tags(pil_image=image)

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
            self.exposure_time = float(value)

        if "FNumber" in exif:
            value = exif["FNumber"]
            self.aperture_size = float(value)
        elif "ApertureValue" in exif:
            value = exif["ApertureValue"]
            self.aperture_size = float(value)

        if "FocalLength" in exif:
            value = exif["FocalLength"]
            self.focal_length = float(value)

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

        self.save()
