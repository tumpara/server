import csv
import io
import urllib.request
from typing import Generator
from urllib.parse import ParseResult, parse_qs
from zipfile import ZipFile

import dateutil.parser
from django.conf import settings
from django.utils.functional import cached_property
from django.utils.timezone import datetime, timezone

from tumpara.storage import register_library_backend
from tumpara.storage.backends import LibraryBackend


@register_library_backend("demo")
class DemoBackend(LibraryBackend):
    def __init__(self, parsed_uri: ParseResult):
        query = parse_qs(parsed_uri.query)

        if "limit" in query:
            if len(query["limit"]) != 1:
                raise ValueError(
                    "The limit parameter for the demo backend must be passed exactly once."
                )
            self.limit = int(query["limit"][0])
        else:
            self.limit = float("inf")

        self.base_path = settings.DATA_ROOT / "demo_backend"
        self.index_path = self.base_path / "index.csv"

    @cached_property
    def index(self):
        dataset_path = self.base_path / "dataset.zip"
        if not dataset_path.is_file():
            urllib.request.urlretrieve(
                "https://unsplash.com/data/lite/latest", dataset_path
            )

        result = {}

        with ZipFile(dataset_path) as dataset_zip:
            with io.TextIOWrapper(dataset_zip.open("photos.tsv000", "r")) as photos_tsv:
                for row in csv.DictReader(photos_tsv, delimiter="\t", quotechar='"'):
                    photo_id = row.pop("photo_id")
                    result[photo_id] = row
                    if len(result) >= self.limit:
                        break

        return result

    def check(self):
        if not self.base_path.is_dir():
            self.base_path.mkdir()

    def walk_files(
        self, start_directory: str = "", *, safe: bool = True
    ) -> Generator[str, None, None]:
        if start_directory != "":
            return
        yield from self.index.keys()

    def exists(self, name: str):
        return name in self.index

    def _ensure_exists(self, name: str):
        if not self.exists(name):
            raise FileNotFoundError(f"file path {name!r} not present in demo backend")

    def get_modified_time(self, name: str):
        if name == "":
            # For the root folder, we return some arbitrary timestamp in the past, so
            # it's modify time is before that of any file. This is:
            # datetime.datetime(1994, 4, 4, 4, 3, 18)
            result = datetime.utcfromtimestamp(765432198)
        else:
            self._ensure_exists(name)
            raw_result = self.index[name]["photo_submitted_at"]
            # Try the regular parsing first, but fall back to dateutil in case the
            # format doesn't match up.
            try:
                result = datetime.strptime(raw_result, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                result = dateutil.parser.parse(raw_result)

        if settings.USE_TZ:
            # Make sure the result is timezone-aware, if applicable.
            result = result.replace(tzinfo=timezone.utc)

        return result

    def open(self, name: str, *args, **kwargs):
        self._ensure_exists(name)

        path = self.base_path / name
        if not path.exists():
            url = f"{self.index[name]['photo_image_url']}?fm=jpg"
            urllib.request.urlretrieve(url, path)
        return open(path, *args, **kwargs)
