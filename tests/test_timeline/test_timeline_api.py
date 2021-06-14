import itertools
from collections import Counter
from datetime import datetime
from typing import Set

from graphene.relay.node import to_global_id
from graphene.test import Client
from hypothesis import assume, given

from tumpara.accounts.models import User
from tumpara.storage.models import Library
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st
from tumpara.timeline.models import Entry

from . import api
from .models import BarEntry, FooEntry


@st.composite
def dataset_strategy(
    draw: st.DataObject.draw, allow_archived: bool = False
) -> st.SearchStrategy[Set[Entry]]:
    library = Library.objects.create(source="file://", context="testing")

    def model_sets(model):
        return st.sets(
            st.from_model(
                FooEntry,
                library=st.just(library),
                timestamp=st.datetimes(datetime(2000, 1, 1), datetime(2020, 1, 1)),
                archived=st.booleans() if allow_archived else st.just(False),
            ),
            min_size=5,
            max_size=15,
        )

    entries = draw(model_sets(FooEntry)) & draw(model_sets(BarEntry))
    return entries


@given(dataset_strategy(allow_archived=True), st.booleans())
def test_entries_query(django_executor, graphql_client: Client, dataset, reverse: bool):
    # Check that there is at least one archived entry which should not appear in the
    # results.
    assume(Entry.objects.filter(archived=True).count() > 0)

    result = graphql_client.execute(
        """
            query TimelineEntries($reverse: Boolean!) {
                timeline(reverse: $reverse) {
                    entries(first: 200) {
                        edges {
                            node {
                                __typename
                                ...on Node {
                                    id
                                }
                                ...on TestTimelineFooEntry {
                                    theString
                                }
                                ...on TestTimelineBarEntry {
                                    firstNumber
                                }
                            }
                        }
                    }
                }
            }
        """,
        variables={"reverse": reverse},
        context=FakeRequestContext(user=User.objects.create_superuser("superuser", "")),
    )
    assert "errors" not in result

    # Build the expected result. Here, we filter out archived entries to test that
    # the filterset is actually working (which, by default, filters out archived
    # items).
    expected_objects = sorted(
        itertools.chain(
            FooEntry.objects.filter(archived=False),
            BarEntry.objects.filter(archived=False),
        ),
        key=lambda obj: obj.timestamp,
        reverse=reverse,
    )
    expected_edges = [
        {
            "node": {
                "__typename": api.FooEntry._meta.name,
                "id": to_global_id(api.FooEntry._meta.name, entry.pk),
                "theString": entry.the_string,
            }
        }
        if isinstance(entry, FooEntry)
        else {
            "node": {
                "__typename": api.BarEntry._meta.name,
                "id": to_global_id(api.BarEntry._meta.name, entry.pk),
                "firstNumber": entry.first_number,
            }
        }
        for entry in expected_objects
    ]

    edges = result["data"]["timeline"]["entries"]["edges"]

    assert edges == expected_edges


@given(dataset_strategy())
def test_distribution_query(django_executor, graphql_client: Client, dataset):
    result = graphql_client.execute(
        """
            query GetTimelineDistribution {
                timeline {
                    yearDistribution {
                        year
                        totalEntryCount
                        monthDistribution {
                            month
                            totalEntryCount
                        }
                    }
                }
            }
        """,  # TODO Also test the startCursor and endCursor fields here
        context=FakeRequestContext(user=User.objects.create_superuser("superuser", "")),
    )
    assert "errors" not in result

    result_year_distribution = Counter()
    result_month_distribution = Counter()
    for year_bucket in result["data"]["timeline"]["yearDistribution"]:
        result_year_distribution.update(
            {year_bucket["year"]: year_bucket["totalEntryCount"]}
        )
        for month_bucket in year_bucket["monthDistribution"]:
            result_month_distribution.update(
                {
                    (year_bucket["year"], month_bucket["month"]): month_bucket[
                        "totalEntryCount"
                    ]
                }
            )

    actual_year_distribution = Counter()
    actual_month_distribution = Counter()
    for entry in Entry.objects.all():
        actual_year_distribution.update({entry.timestamp.year: 1})
        actual_month_distribution.update(
            {(entry.timestamp.year, entry.timestamp.month): 1}
        )

    assert result_year_distribution == actual_year_distribution
    assert result_month_distribution == actual_month_distribution
