from graphene.relay.node import from_global_id, to_global_id
from graphene.test import Client
from hypothesis import assume, given, settings

from tumpara.accounts.models import AnonymousUser, GenericUser, User
from tumpara.testing import FakeRequestContext
from tumpara.testing import strategies as st
from tumpara.timeline import api as timeline_api
from tumpara.timeline.api.albums import AlbumForm
from tumpara.timeline.models import Album

update_album_mutation = """
    mutation UpdateAlbum($id: ID, $name: String!, $archived: Boolean!) {
        updateTimelineAlbum(
            input : {
                id: $id,
                name: $name,
                archived: $archived
            }
        ) {
            album {
                id
            }
        }
    }
"""

create_album_mutation = """
    mutation CreateAlbum($name: String!, $archived: Boolean!) {
        createTimelineAlbum(
            input : {
                name: $name,
                archived: $archived
            }
        ) {
            album {
                id
            }
        }
    }
"""


@settings(max_examples=1)
@given(
    st.from_model(Album),
    st.from_model(User),
    st.from_model(User),
    st.builds(AnonymousUser),
)
def test_disallowed_editing(
    django_executor,
    graphql_client: Client,
    album: Album,
    other: User,
    member: User,
    anonymous: AnonymousUser,
):
    """Non-owners are not allowed to perform edits."""
    assume(other != member)
    album.add_user(member)

    def check_access(user: GenericUser):
        result = graphql_client.execute(
            update_album_mutation,
            variables={
                "id": to_global_id(timeline_api.Album._meta.name, album.pk),
                "name": "bla",
                "archived": True,
            },
            context=FakeRequestContext(user=user),
        )
        assert "errors" in result
        assert len(result["errors"]) == 1
        assert "permission" in result["errors"][0]["message"]

    check_access(other)
    check_access(member)
    check_access(anonymous)


@given(
    st.from_model(Album),
    st.from_form(AlbumForm),
    st.from_model(User, is_staff=st.booleans(), is_superuser=st.booleans()),
)
def test_editing(
    django_executor,
    graphql_client: Client,
    album: Album,
    form: AlbumForm,
    user: User,
):
    """Owners and superusers can successfully perform edits."""
    assume({"name": album.name, "archived": album.archived} != form.data)
    if not user.is_superuser:
        album.add_user(user, owner=True)

    result = graphql_client.execute(
        update_album_mutation,
        variables={
            "id": to_global_id(timeline_api.Album._meta.name, album.pk),
            "name": form.data["name"],
            "archived": form.data["archived"],
        },
        context=FakeRequestContext(user=user),
    )
    assert "errors" not in result

    album.refresh_from_db()
    assert album.name == form.data["name"].strip()
    assert album.archived == form.data["archived"]


@given(st.from_form(AlbumForm), st.builds(AnonymousUser))
def test_anonymous_creating(
    django_executor, graphql_client: Client, form: AlbumForm, user: AnonymousUser
):
    """Anonymous users cannot create forms."""
    result = graphql_client.execute(
        create_album_mutation,
        variables={
            "name": form.data["name"],
            "archived": form.data["archived"],
        },
        context=FakeRequestContext(user=user),
    )
    assert "errors" in result
    assert len(result["errors"]) == 1
    assert "permission" in result["errors"][0]["message"]


@given(st.from_form(AlbumForm), st.from_model(User))
def test_creating(django_executor, graphql_client: Client, form: AlbumForm, user: User):
    """Users can create forms which they then own."""
    result = graphql_client.execute(
        create_album_mutation,
        variables={
            "name": form.data["name"],
            "archived": form.data["archived"],
        },
        context=FakeRequestContext(user=user),
    )
    assert "errors" not in result

    _, pk = from_global_id(result["data"]["createTimelineAlbum"]["album"]["id"])
    album = Album.objects.get(pk=pk)
    assert album.name == form.data["name"].strip()
    assert album.archived == form.data["archived"]
    assert album.is_owner(user)
