from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Generic, Sequence, TypeVar, Union

from django.db import models
from django.db.models.base import ModelBase
from django.db.models.fields import related_descriptors
from django.utils.translation import gettext_lazy as _

from tumpara.accounts.models import MembershipHost

if TYPE_CHECKING:
    from django.db.models.expressions import Combinable
    from django.db.models.manager import RelatedManager


C = TypeVar("C", bound="Collection")
T = TypeVar("T", bound="models.Model")


class BaseCollection(ModelBase):
    def __new__(mcs, name, bases, attrs, **kwargs):
        new_class = super().__new__(mcs, name, bases, attrs, **kwargs)

        # Assure initialization is only performed for actual subclasses of Collection.
        parents = [b for b in bases if isinstance(b, BaseCollection)]
        if not parents:
            return new_class

        assert (
            isinstance(
                getattr(new_class, "items", None),
                related_descriptors.ManyToManyDescriptor,
            )
            # The second condition here ensures that the ManyToManyField has actually
            # been overridden and the default 'self' relation is gone.
            and new_class.items.field.remote_field.model != new_class
            # TODO Check that the through field is an instance of CollectionItem
        ), (
            "Subclasses of Collection must provide a many to many field to their "
            "object type through the corresponding CollectionItem type called 'items'."
        )
        return new_class


class Collection(Generic[T], models.Model, metaclass=BaseCollection):
    """Collections group objects into distinct groups.

    Examples of collection types could be 'Tag' or 'Album', but more specific
    collections are also possible. To define a new type of collection, subclass this
    model as well as :class:`CollectionItem` accordingly.

    Models that inherit from this type need to override the `items` field containing
    the actual item objects. This field should reference the type of Model the
    collection holds, through a subclass of the :class:`CollectionItem`.
    """

    items: models.ManyToManyField[Sequence[T], RelatedManager[T]]

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)


class BaseCollectionItem(ModelBase):
    def __new__(mcs, name, bases, attrs, **kwargs):
        new_class = super().__new__(mcs, name, bases, attrs, **kwargs)

        # Assure initialization is only performed for actual subclasses of
        # CollectionItem.
        parents = [b for b in bases if isinstance(b, BaseCollectionItem)]
        if not parents:
            return new_class

        assert isinstance(
            getattr(new_class, "collection", None),
            related_descriptors.ForwardManyToOneDescriptor,
        ), (
            "Subclasses of CollectionItem must provide a foreign key to their "
            "collection type called 'collection'."
        )
        assert issubclass(new_class.collection.field.remote_field.model, Collection), (
            "The model for the 'collection' foreign key must be a subclass of "
            "Collection. "
        )
        return new_class


class CollectionItem(Generic[C], models.Model, metaclass=BaseCollectionItem):
    """Relationship of an object to a collection.

    Models that inherit from this type need to define two required fields:
    - A foreign key called `collection` that references the concrete implementation of
      :class:`Collection` the item is for.
    - Some attribute that links to the actual object put into the collection. This
      should mainly be a foreign key.
    """

    collection: models.ForeignKey[Union[C, Combinable], C]

    class Meta:
        abstract = True


class Archivable(models.Model):
    archived = models.BooleanField(
        _("archived status"),
        default=False,
        help_text=_(
            "Determines whether this item has been marked as archived. Clients are "
            "advised to filter out archived items, unless explicitly asked for."
        ),
    )

    class Meta:
        abstract = True
