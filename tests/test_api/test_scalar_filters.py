from typing import Union

import pytest
from django.core.exceptions import ValidationError
from django.db.models import Q
from hypothesis import given

from tumpara.api.filtering import NumericFilter
from tumpara.testing import FakeResolveInfo
from tumpara.testing import strategies as st


@st.composite
def floats_or_ints(
    draw: st.DataObject.draw, min_value: float = -9e18
) -> st.SearchStrategy[Union[int, float]]:
    if draw(st.booleans()):
        return draw(
            st.floats(
                allow_nan=False,
                allow_infinity=False,
                # These limits make sure we are inside of SQLite's integer limit:
                # https://stackoverflow.com/a/57465877
                min_value=float(min_value),
                max_value=float(9e18),
            )
        )
    else:
        return draw(st.integers(int(min_value), int(9e18)))


@st.composite
def numeric_ranges(draw):
    result = {}
    if draw(st.booleans()):
        result["minimum"] = draw(floats_or_ints())
    else:
        result["maximum"] = draw(floats_or_ints())
    if "maximum" not in result and draw(st.booleans()):
        result["maximum"] = draw(floats_or_ints(min_value=result["minimum"]))
    return result


def test_invalid():
    """Invalid configurations throw a ValidationError."""
    with pytest.raises(ValidationError):
        filter: NumericFilter = NumericFilter._meta.container(
            {"value": 5, "minimum": 5}
        )
        filter.build_query(FakeResolveInfo(), "test")


@given(st.field_prefix(), floats_or_ints())
def test_exact(prefix: str, value: Union[int, float]):
    """Exact value filters return the correct query."""
    filter: NumericFilter = NumericFilter._meta.container({"value": value})
    assert filter.build_query(FakeResolveInfo(), prefix) == Q(
        **{f"{prefix}__exact": value}
    )


@given(st.field_prefix(), numeric_ranges())
def test_range(prefix: str, range: dict):
    """Range value filters return the correct query."""
    filter: NumericFilter = NumericFilter._meta.container(range)
    query = filter.build_query(FakeResolveInfo(), prefix)
    if "minimum" in range:
        assert (f"{prefix}__gte", range["minimum"]) in query.children
    if "maximum" in range:
        assert (f"{prefix}__lte", range["maximum"]) in query.children
    assert len(query) == len(range)
