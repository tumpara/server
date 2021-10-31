import os.path
import shutil
from collections import defaultdict

from django.conf import settings as django_settings
from hypothesis import given, settings

from tumpara.content.gallery.models import AutodevelopedPhoto, Photo, RawPhoto
from tumpara.storage.models import Library
from tumpara.testing import strategies as st


def get_test_photo_paths() -> list[tuple[str, str]]:
    directory = os.path.join(django_settings.TESTDATA_ROOT, "raws")

    # We assume that the directory contains a bunch of .JPG files, with each of them
    # having exactly one corresponding raw file (in whatever format the camera
    # produces). We want to now map these 1:1. This dictionary will contain path
    # prefixes as the key and a list of extensions for all the files we have as the
    # value, like this:
    #   { "/path/to/testdata/raws/IMG_0009": [".CR2", ".JPG"] }
    # The example above means that the testdata folder contains a IMG_0009.CR2 raw file
    # with the corresponding developed IMG_0009.JPG file.
    mappings = defaultdict(list)

    for name in os.listdir(directory):
        base, extension = os.path.splitext(os.path.join(directory, name))
        # We want the developed files to be last in the list.
        if extension.lower() in (".jpg", ".jpeg", ".tiff", ".tif"):
            mappings[base].append(extension)
        else:
            mappings[base].insert(0, extension)

    assert all(len(extensions) == 2 for extensions in mappings.values()), (
        "For each raw file, exactly one developed regular image must be provided in "
        "the testing dataset. "
    )

    return [
        (base + extensions[0], base + extensions[1])
        for base, extensions in mappings.items()
    ]


test_photo_strategy = st.sampled_from(get_test_photo_paths())


@settings(deadline=25000, max_examples=15)
@given(
    st.temporary_directories(),
    st.lists(test_photo_strategy, min_size=2, max_size=4, unique=True),
    st.data(),
)
def test_raw_autodeveloping(
    django_executor, root: str, paths: set[tuple[str, str]], data: st.DataObject
):
    """Raw photos are correctly autodeveloped, if no corresponding regular image is
    found."""
    library = Library.objects.create(context="timeline", source=f"file://{root}")
    for model in (AutodevelopedPhoto, Photo, RawPhoto):
        assert model.active_objects.count() == 0

    # We do this test a few times to make sure that the scanner correctly processes
    # changes.
    for _ in range(data.draw(st.integers(2, 4))):
        # For each photo, draw if we want to use the provided rendition (True) or if
        # we want Tumpara to automatically generate one (False).
        use_renditions = data.draw(
            st.lists(st.booleans(), min_size=len(paths), max_size=len(paths))
        )
        occupied_filenames = set()

        for (raw_path, developed_path), use_rendition in zip(paths, use_renditions):
            raw_filename = data.draw(
                st.filenames(
                    exclude=occupied_filenames,
                    suffix=os.path.splitext(raw_path)[1],
                ),
            )
            occupied_filenames.add(raw_filename)
            shutil.copy(raw_path, os.path.join(root, raw_filename))

            # Only copy the provided rendition into the library's folder if we want to
            # use it. In the other case, we want an automatically rendered Photo to
            # be created.
            if use_rendition:
                developed_filename = data.draw(
                    st.filenames(
                        exclude=occupied_filenames,
                        suffix=os.path.splitext(developed_path)[1],
                    )
                )
                occupied_filenames.add(developed_filename)
                shutil.copy(developed_path, os.path.join(root, developed_filename))

        library.scan()

        assert RawPhoto.active_objects.count() == len(paths)
        assert Photo.active_objects.count() == sum(use_renditions)
        assert AutodevelopedPhoto.active_objects.count() == len(paths) - sum(
            use_renditions
        )

        # Clear all files in the folder so that we can refill it in the next iteration.
        for filename in os.listdir(root):
            os.unlink(os.path.join(root, filename))
