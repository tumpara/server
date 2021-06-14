from datetime import datetime, timedelta

from django.test import Client as DjangoClient
from freezegun import freeze_time
from graphene.relay.node import to_global_id
from graphene.test import Client as GrapheneClient
from hypothesis import given

from tumpara.testing import strategies as st

from . import api
from .models import GenericPreviewable

get_previewable_mutation = """
    query GetPreviewable($id: ID!, $width: Int!, $height: Int!) {
        node(id: $id) {
            ...on ImagePreviewable {
                imagePreviewUrl(width: $width, height: $height)
            }
        }
    }
"""


@given(st.from_model(GenericPreviewable), st.graphql_ints(), st.graphql_ints())
def test_image_preview(
    django_executor,
    graphql_client: GrapheneClient,
    previewable: GenericPreviewable,
    width: int,
    height: int,
):
    """An image preview can successfully be rendered and downloaded and is no longer
    available an hour later."""
    result = graphql_client.execute(
        get_previewable_mutation,
        variables={
            "id": to_global_id(api.GenericPreviewable._meta.name, previewable.pk),
            "width": width,
            "height": height,
        },
    )
    assert "errors" not in result
    url = result["data"]["node"]["imagePreviewUrl"]

    client = DjangoClient()
    response = client.get(url)
    assert response.status_code == 200
    content = b"".join(response.streaming_content).decode()
    assert content == f"{width}x{height}"

    with freeze_time(datetime.now() + timedelta(hours=1, seconds=2)):
        response = client.get(url)
        assert response.status_code == 404
