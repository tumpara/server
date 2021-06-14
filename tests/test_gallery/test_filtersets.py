from typing import Set

from hypothesis import given

from tumpara.api.filtering import NumericFilter
from tumpara.content.gallery.api.filtersets import PhotoFilterSet
from tumpara.content.gallery.models import Photo
from tumpara.storage.models import Library
from tumpara.testing import strategies as st

from ..test_timeline.test_entry_filtersets import check_results


@st.composite
def datasets(draw: st.DataObject.draw) -> st.SearchStrategy[Set[Photo]]:
    library = Library.objects.create(source="file://", context="testing")
    return draw(
        st.sets(
            st.from_model(Photo, library=st.just(library), archived=st.just(False)),
            min_size=2,
        )
    )


@given(datasets())
def test_width_filtering(django_executor, photos: Set[Photo]):
    """The width filter gets passed along correctly."""
    # Using the median value as the limiting value here makes sure that at least one
    # photo is filtered out and at least one stays in.
    median_value = sorted(photos, key=lambda photo: photo.width)[
        int(len(photos) / 2)
    ].width
    check_results(
        {photo for photo in photos if photo.width >= median_value},
        types=["Photo"],
        photo_filters=PhotoFilterSet._meta.container(
            width=NumericFilter._meta.container(minimum=median_value)
        ),
    )


@given(datasets())
def test_height_filtering(django_executor, photos: Set[Photo]):
    """The height filter gets passed along correctly."""
    median_value = sorted(photos, key=lambda photo: photo.height)[
        int(len(photos) / 2)
    ].height
    check_results(
        {photo for photo in photos if photo.height >= median_value},
        types=["Photo"],
        photo_filters=PhotoFilterSet._meta.container(
            height=NumericFilter._meta.container(minimum=median_value)
        ),
    )


@given(datasets())
def test_smaller_axis_filtering(django_executor, photos: Set[Photo]):
    """The filter for the smaller axis gets passed along correctly."""
    median_photo = sorted(photos, key=lambda photo: min(photo.width, photo.height))[
        int(len(photos) / 2)
    ]
    median_value = min(median_photo.width, median_photo.height)
    check_results(
        {photo for photo in photos if min(photo.width, photo.height) >= median_value},
        types=["Photo"],
        photo_filters=PhotoFilterSet._meta.container(
            smaller_axis=NumericFilter._meta.container(minimum=median_value)
        ),
    )


@given(datasets())
def test_larger_axis_filtering(django_executor, photos: Set[Photo]):
    """The filter for the larger axis gets passed along correctly."""
    median_photo = sorted(photos, key=lambda photo: max(photo.width, photo.height))[
        int(len(photos) / 2)
    ]
    median_value = max(median_photo.width, median_photo.height)
    check_results(
        {photo for photo in photos if max(photo.width, photo.height) >= median_value},
        types=["Photo"],
        photo_filters=PhotoFilterSet._meta.container(
            larger_axis=NumericFilter._meta.container(minimum=median_value)
        ),
    )


@given(datasets())
def test_megapixel_filtering(django_executor, photos: Set[Photo]):
    """The megapixel count filter gets passed along correctly."""
    median_value = sorted(photos, key=lambda photo: photo.megapixels)[
        int(len(photos) / 2)
    ].megapixels
    check_results(
        {photo for photo in photos if photo.megapixels >= median_value},
        types=["Photo"],
        photo_filters=PhotoFilterSet._meta.container(
            megapixels=NumericFilter._meta.container(minimum=median_value)
        ),
    )
