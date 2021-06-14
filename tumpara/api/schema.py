import graphene
from django.conf import settings
from graphene import relay
from graphene_django.debug import DjangoDebug

from ..api import Subschema, registered_subschemas

__all__ = ["root"]


def build_schema():
    queries = []
    mutations = []
    types = []

    def load_subschema(subschema: Subschema):
        if subschema.query:
            queries.append(subschema.query)
        if subschema.mutation:
            mutations.append(subschema.mutation)
        if subschema.types:
            types.extend(subschema.types)

    deferred_subschemas = []
    for subschema in registered_subschemas:
        if callable(subschema):
            # Defer this subschema and load it once all other non-deferred entries
            # have be processed.
            deferred_subschemas.append(subschema)
            continue
        load_subschema(subschema)
    for subschema in deferred_subschemas:
        load_subschema(subschema())

    query_base = {
        "node": relay.Node.Field(),
    }
    query_base["node"].description = "Resolve a node using its ID."
    if (
        settings.DEBUG
        and "graphene_django.debug.DjangoDebugMiddleware"
        in settings.GRAPHENE["MIDDLEWARE"]
    ):
        query_base["debug"] = graphene.Field(DjangoDebug, name="debug")

    return graphene.Schema(
        query=type("Query", tuple(queries), query_base),
        mutation=type("Mutation", tuple(mutations), {}),
        types=types,
    )


root = build_schema()
