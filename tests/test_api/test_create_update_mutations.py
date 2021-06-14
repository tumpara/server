from graphene.relay.node import from_global_id, to_global_id
from graphene.test import Client
from hypothesis import HealthCheck, assume, given, settings

from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st

from . import api
from .models import Thing

UpdateForm = api.UpdateThing._meta.form_class

create_mutation = """
    mutation CreateThing($input: TestApiCreateThingInput!) {
        testApiCreateThing(
            input: $input
        ) {
            thing {
                id
            }
        }
    }
"""

update_mutation = """
    mutation UpdateAlbum($input: TestApiUpdateThingInput!) {
        testApiUpdateThing(
            input: $input
        ) {
            thing {
                id
            }
        }
    }
"""


def test_updated_form():
    """The form for update mutations has been modified so that fields are no longer
    required."""
    for field in api.ThingForm().fields.values():
        assert field.required
    for field in UpdateForm().fields.values():
        assert not field.required


@given(st.from_form(api.ThingForm), st.from_model(User))
def test_creating(
    django_executor, graphql_client: Client, form: api.ThingForm, user: User
):
    """Creating a thing is not allowed for anonymous users. For others, data is applied
    correctly and the user is made a member."""
    result = graphql_client.execute(
        create_mutation,
        variables={"input": form.data},
        context=FakeRequestContext(user=AnonymousUser()),
    )
    assert "errors" in result
    assert len(result["errors"]) == 1
    assert "permission" in result["errors"][0]["message"]

    result = graphql_client.execute(
        create_mutation,
        variables={"input": form.data},
        context=FakeRequestContext(user=user),
    )
    assert "errors" not in result

    _, pk = from_global_id(result["data"]["testApiCreateThing"]["thing"]["id"])
    thing = Thing.objects.get(pk=pk)
    assert thing.foo == form.data["foo"].strip()
    assert thing.bar == form.data["bar"].strip()
    assert thing.is_owner(user)


@given(st.from_model(Thing), st.from_form(api.ThingForm), st.from_model(User))
def test_updating(
    django_executor,
    graphql_client: Client,
    thing: Thing,
    form: api.ThingForm,
    user: User,
):
    """Updating a thing is only allowed for owners. After the mutation is done, the new
    data has been saved."""
    assume(thing.foo != form.data["foo"])
    assume(thing.bar != form.data["bar"])

    mutation_variables = {
        "input": {**form.data, "id": to_global_id(api.Thing._meta.name, thing.pk)}
    }

    def check_access_rejected(user: GenericUser):
        result = graphql_client.execute(
            update_mutation,
            variables=mutation_variables,
            context=FakeRequestContext(user=user),
        )
        assert "errors" in result
        assert len(result["errors"]) == 1
        assert "permission" in result["errors"][0]["message"]

    check_access_rejected(AnonymousUser())
    check_access_rejected(user)
    thing.add_user(user)
    check_access_rejected(user)

    thing.add_user(user, owner=True)

    result = graphql_client.execute(
        update_mutation,
        variables=mutation_variables,
        context=FakeRequestContext(user=user),
    )
    assert "errors" not in result

    thing.refresh_from_db()
    assert thing.foo == form.data["foo"].strip()
    assert thing.bar == form.data["bar"].strip()


@settings(suppress_health_check=HealthCheck.all())
@given(
    st.from_model(Thing), st.from_field(Thing.foo.field), st.booleans(), st.superusers()
)
def test_partial_updates(
    django_executor,
    graphql_client: Client,
    thing: Thing,
    new_value: str,
    update_foo: bool,
    user: User,
):
    """Partial updates work as expected, keeping the untouched data as-is."""
    key = "foo" if update_foo else "bar"
    new_value = new_value.strip()

    assume(getattr(thing, key) != new_value)

    result = graphql_client.execute(
        update_mutation,
        variables={
            "input": {
                "id": to_global_id(api.Thing._meta.name, thing.pk),
                key: new_value,
            }
        },
        context=FakeRequestContext(user=user),
    )
    assert "errors" not in result

    old_foo = thing.foo.strip()
    old_bar = thing.bar.strip()
    thing.refresh_from_db()
    if update_foo:
        assert thing.foo == new_value
        assert thing.bar == old_bar
    else:
        assert thing.foo == old_foo
        assert thing.bar == new_value
