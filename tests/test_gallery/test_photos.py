import importlib.util
import os.path
from contextlib import contextmanager
from typing import List
from unittest import mock

import PIL.Image
import pytest
from django.conf import settings as django_settings
from hypothesis import given, settings

from tumpara.content.gallery.models import Photo, RawPhoto
from tumpara.storage.models import InvalidFileTypeError, Library
from tumpara.testing import strategies as st


def get_test_library_index() -> List[dict]:
    index_filename = os.path.join(django_settings.TESTDATA_ROOT, "index.py")
    spec = importlib.util.spec_from_file_location("test_library.index", index_filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return [{"path": item[0], **item[1]} for item in module.index.items()]


test_library_strategy = st.sampled_from(get_test_library_index())


@contextmanager
def mocked_photo_from_index(info: dict) -> Photo:
    full_path = os.path.join(django_settings.TESTDATA_ROOT, "library", info["path"])
    assert os.path.isfile(full_path)

    class MockFile:
        path = info["path"]

        def open(self, mode="rb"):
            return open(full_path, mode)

    library = Library(
        source=f"file://{os.path.join(django_settings.TESTDATA_ROOT, 'library')}"
    )

    try:
        file_patch = mock.patch.object(Photo, "file", new=MockFile())
        file_patch.start()
        photo = Photo(library=library)
        save_patch = mock.patch.object(photo, "save")
        save_patch.start()
        manager_get_patch = mock.patch.object(
            RawPhoto.objects, "get", new=lambda **kwargs: None
        )
        manager_get_patch.start()
        photo.scan_from_file()
        yield photo
    finally:
        save_patch.stop()
        file_patch.stop()
        manager_get_patch.stop()


@given(test_library_strategy)
def test_handler_accepts(info: dict):
    """The handler accepts the file as valid."""
    library = Library(
        source=f"file://{os.path.join(django_settings.TESTDATA_ROOT, 'library')}"
    )

    try:
        Photo.analyze_file(library, info["path"])
    except InvalidFileTypeError:
        pytest.fail("Photo.analyze_file() rejected the image")


@settings(deadline=1000)
@given(test_library_strategy)
def test_scanned_metadata(info: dict):
    """The metadata extracted from the file scan corresponds to the data in the
    index."""
    with mocked_photo_from_index(info) as photo:
        # Mock the RawPhoto manager so that the photo can't scan for RAW counterparts
        # right now.
        photo.scan_from_file(slow=False)

        for key, value in info["metadata"].items():
            if isinstance(value, float):
                precision = 4 if key == "exposure_time" else 1
                assert (
                    abs((getattr(photo, key) - value)) * precision <= 1
                ), f"{key} metadata entry does not match for file {info['filename']}"
            else:
                assert (
                    getattr(photo, key) == value
                ), f"{key} metadata entry does not match for file {info['filename']}"


@settings(deadline=10000, max_examples=10)
@given(
    test_library_strategy,
    st.integers(min_value=1, max_value=8000),
    st.integers(min_value=1, max_value=8000),
    st.sampled_from(("jpeg", "webp")),
)
def test_preview_image(info: dict, width: int, height: int, format: str):
    """The photo correctly renders different preview images."""
    with mocked_photo_from_index(info) as photo:
        image = photo.render_preview_image(width, height, format)
        image = PIL.Image.open(image)
        assert 0 < image.width <= width or photo.width
        assert 0 < image.height <= height or photo.height
