from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.accounts.api import MembershipHost
from tumpara.api import Subschema
from tumpara.collections.api import (
    Archivable,
    ArchivableFilterSet,
    Collection,
    CollectionsFilter,
)

from . import models


class ThingFilterSet(ArchivableFilterSet):
    pass


class Thing(DjangoObjectType):
    class Meta:
        name = "TestTaxonomiesThing"
        model = models.Thing
        interfaces = (relay.Node, Archivable)


class ThingContainer(DjangoObjectType):
    class Meta:
        name = "TestTaxonomiesThingContainer"
        model = models.ThingContainer
        interfaces = (relay.Node, Collection)


class ThingContainerMembers(DjangoObjectType):
    class Meta:
        name = "TestTaxonomiesThingContainerMembers"
        model = models.ThingContainerMembers
        interfaces = (relay.Node, Collection, MembershipHost)


class MaybeHiddenThing(DjangoObjectType):
    class Meta:
        name = "TestTaxonomiesMaybeHiddenThing"
        model = models.MaybeHiddenThing
        interfaces = (relay.Node,)


subschema = Subschema(
    types=[Thing, ThingContainer, ThingContainerMembers, MaybeHiddenThing]
)
