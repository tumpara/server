from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.api import Subschema
from tumpara.storage.api import LibraryContent

from . import models


class Thing(DjangoObjectType):
    class Meta:
        name = "TestStorageThing"
        model = models.Thing
        interfaces = (relay.Node, LibraryContent)


subschema = Subschema(types=[Thing])
