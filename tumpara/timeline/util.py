from os import path
from typing import Callable

from dateutil.parser import parse as dateutil_parse
from django.utils import timezone

from tumpara.storage.models import File


def parse_timestamp_from_filename(
    file: File, fallback: Callable[[], timezone.datetime] = timezone.now
) -> timezone.datetime:
    """Try to parse a timestamp from a filename.

    :param fallback: A function that will be called when parsing fails. Whatever this
        function returns will be returned.
    """
    try:
        basename = path.basename(file.path)
        return dateutil_parse(basename, fuzzy=True, ignoretz=True)
    except ValueError:
        return fallback()
