from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.api import Subschema
from tumpara.multimedia.api import ImagePreviewable

from . import models


class GenericPreviewable(DjangoObjectType):
    class Meta:
        name = "TestMultimediaGenericPreviewable"
        model = models.GenericPreviewable
        interfaces = (relay.Node, ImagePreviewable)


subschema = Subschema(types=[GenericPreviewable])
