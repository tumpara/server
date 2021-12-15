import typing
from typing import Union
from uuid import UUID

from django.db import models

__all__ = ["pk_type", "map_object_to_primary_key"]

pk_type = Union[int, str, UUID]


def map_object_to_primary_key(
    item: Union[models.Model, pk_type],
    model_type=None,
    error_message: str = "object lookup",
) -> pk_type:
    """Map a given object to it's primary key. The object may be provided as a model
    instance or as the primary key itself."""
    if isinstance(item, typing.get_args(pk_type)):
        return item

    if model_type is not None:
        if isinstance(item, model_type):
            return item.pk
        elif isinstance(item, models.Model):
            raise TypeError(
                f"{error_message} for type {model_type.__name__} requires "
                f"providing objects of that type (received type {type(item).__name__!r})"
            )
    else:
        if isinstance(item, models.Model):
            return item.pk

    raise TypeError(
        f"{error_message} requires objects to be provided either as model instances or "
        f"via their primary keys (got type {type(item).__name__!r})"
    )
