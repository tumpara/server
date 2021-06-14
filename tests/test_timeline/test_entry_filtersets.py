from django.db.models import F
from hypothesis import assume, given

from tumpara.storage.models import Library
from tumpara.testing import FakeResolveInfo
from tumpara.testing import strategies as st
from tumpara.timeline.api.timeline_view import EntryFilterSet
from tumpara.timeline.models import Entry

from .api import BarEntryFilterSet, FooEntryFilterSet
from .models import BarEntry, FooEntry


@st.composite
def dataset_strategy(
    draw: st.DataObject.draw, **kwargs
) -> st.SearchStrategy[set[Entry]]:
    kwargs.setdefault("min_size", 5)
    kwargs.setdefault("max_size", 10)

    library, _ = Library.objects.get_or_create(source="file://", context="testing")

    model_strategies = []
    for model in (FooEntry, BarEntry):
        model_strategy = st.from_model(
            model,
            library=st.just(library),
            archived=st.booleans(),
            visibility=st.integers(min_value=Entry.PUBLIC, max_value=Entry.OWNERS),
            stack_key=st.just(None),
            stack_representative=st.just(False),
        )
        model_strategies.append(model_strategy)
    return draw(st.sets(st.one_of(model_strategies), **kwargs))


def check_results(expected_results, **filterset_kwargs):
    if not isinstance(expected_results, set):
        expected_results = set(expected_results)

    filterset = EntryFilterSet._meta.container(**filterset_kwargs)
    queryset = filterset.prepare_queryset(Entry.objects.get_queryset()).filter(
        filterset.build_query(FakeResolveInfo())
    )
    results = {entry.implementation for entry in queryset}

    assert results == expected_results


@given(dataset_strategy(), st.booleans(), st.booleans(), st.booleans())
def test_foo_filtering(
    django_executor,
    dataset,
    include_archived: bool,
    only_archived: bool,
    contains_alpha: bool,
):
    assume(False in (include_archived, only_archived))

    expected_queryset = FooEntry.objects.all()
    if contains_alpha:
        expected_queryset = expected_queryset.filter(the_string__regex=r"[a-zA-Z]")

    if only_archived:
        expected_queryset = expected_queryset.filter(archived=True)
    elif not include_archived:
        expected_queryset = expected_queryset.filter(archived=False)

    check_results(
        expected_queryset,
        types=["FooEntry"],
        include_archived=include_archived,
        only_archived=only_archived,
        fooentry_filters=FooEntryFilterSet._meta.container(
            contains_alpha=contains_alpha
        ),
    )


@given(
    dataset_strategy(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)
def test_bar_filtering(
    django_executor,
    dataset,
    include_archived: bool,
    only_archived: bool,
    large: bool,
    product_positive: bool,
):
    assume(False in (include_archived, only_archived))

    expected_queryset = BarEntry.objects.all()
    if large:
        expected_queryset = expected_queryset.filter(first_number__gt=50)
    if product_positive:
        expected_queryset = expected_queryset.annotate(
            product=F("first_number") * F("second_number")
        ).filter(product__gt=0)

    if only_archived:
        expected_queryset = expected_queryset.filter(archived=True)
    elif not include_archived:
        expected_queryset = expected_queryset.filter(archived=False)

    check_results(
        expected_queryset,
        types=["BarEntry"],
        include_archived=include_archived,
        only_archived=only_archived,
        barentry_filters=BarEntryFilterSet._meta.container(
            large=large, product_positive=product_positive
        ),
    )


@given(
    dataset_strategy(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)
def test_both_filtering(
    django_executor,
    dataset,
    include_archived: bool,
    only_archived: bool,
    contains_alpha: bool,
    large: bool,
):
    assume(False in (include_archived, only_archived))

    foo_queryset = FooEntry.objects.all()
    if contains_alpha:
        foo_queryset = foo_queryset.filter(the_string__regex=r"[a-zA-Z]")

    bar_queryset = BarEntry.objects.all()
    if large:
        bar_queryset = bar_queryset.filter(first_number__gt=50)

    if only_archived:
        foo_queryset = foo_queryset.filter(archived=True)
        bar_queryset = bar_queryset.filter(archived=True)
    elif not include_archived:
        foo_queryset = foo_queryset.filter(archived=False)
        bar_queryset = bar_queryset.filter(archived=False)

    check_results(
        set(foo_queryset) | set(bar_queryset),
        include_archived=include_archived,
        only_archived=only_archived,
        fooentry_filters=FooEntryFilterSet._meta.container(
            contains_alpha=contains_alpha
        ),
        barentry_filters=BarEntryFilterSet._meta.container(large=large),
    )
