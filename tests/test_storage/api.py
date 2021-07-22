from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.api import Subschema
from tumpara.storage.api import FileHandler, LibraryContent

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


class Thing(DjangoObjectType):
    class Meta:
        name = "TestStorageThing"
        model = models.Thing
        interfaces = (relay.Node, LibraryContent)


subschema = Subschema(types=[GenericFile, Thing])
