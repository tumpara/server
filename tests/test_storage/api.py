from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.api import Subschema
from tumpara.storage.api import (
    FileHandler,
    LibraryContentFilterSet,
    LibraryContentObjectType,
)

from . import models


class GenericFile(DjangoObjectType):
    class Meta:
        name = "TestStorageGenericFile"
        model = models.GenericFileHandler
        fields = ("initialized",)
        interfaces = (relay.Node, FileHandler)

    # Here, we explicitly don't add a get_queryset() method that returns only active,
    # non-orphaned file handlers because then we can test that links for orphaned file
    # objects don't work.


class Thing(LibraryContentObjectType):
    class Meta:
        name = "TestStorageThing"
        model = models.Thing


class ThingFilterSet(LibraryContentFilterSet):
    pass


subschema = Subschema(types=[GenericFile, Thing])
