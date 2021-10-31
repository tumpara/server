from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Type, Union

# Import the graphene_gis module when initializing the schema to make sure that
# GeoDjango fields are serialized correctly and don't error out.
import graphene_gis.converter  # noqa: F401
from graphene import ObjectType
from graphene.types.base import BaseType


@dataclass
class Subschema:
    query: Optional[Type[ObjectType]] = None
    mutation: Optional[Type[ObjectType]] = None
    types: Optional[Sequence[Type[BaseType]]] = None


PotentiallyDeferredSubschema = Union[Subschema, Callable[[], Subschema]]

registered_subschemas = list[PotentiallyDeferredSubschema]()


def register_subschema(subschema: PotentiallyDeferredSubschema):
    """Register a subschema to the API.

    When building the final GraphQL schema, all these subschemas are merged together
    into the final spec. This is inteaded to be called from the `ready()` method in
    the corresponding AppConfig.

    The subschema may either be provided directly or as a callable. The latter type
    are deferred subschemas. These will be initialized last, giving other apps the
    possibility to load potential side effects first (an example for this pattern is
    the timeline's entry filter framework).
    """
    assert isinstance(subschema, Subschema) or callable(subschema), (
        f"Subschemas must either be provided directly or wrapped in a callable (got "
        f"{type(subschema)!r})."
    )
    registered_subschemas.append(subschema)
