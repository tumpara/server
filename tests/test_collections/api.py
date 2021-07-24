import graphene
from django.db.models import QuerySet
from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.accounts.api import MembershipHostObjectType
from tumpara.accounts.models import GenericUser
from tumpara.api import Subschema
from tumpara.collections.api import Archivable, ArchivableFilterSet, Collection
from tumpara.storage.api import LibraryContentObjectType

from . import models


class ThingFilterSet(ArchivableFilterSet):
    pass


class Thing(DjangoObjectType):
    class Meta:
        name = "TestCollectionsThing"
        model = models.Thing
        interfaces = (relay.Node, Archivable)

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        if writing:
            user: GenericUser = info.context.user
            if not user.is_authenticated or not user.is_active:
                queryset = queryset.none()
        return queryset


class ThingContainer(DjangoObjectType):
    class Meta:
        name = "TestCollectionsThingContainer"
        model = models.ThingContainer
        interfaces = (relay.Node, Collection)

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        if writing:
            user: GenericUser = info.context.user
            if not user.is_authenticated or not user.is_active:
                queryset = queryset.none()
        return queryset


class ThingContainerMembers(MembershipHostObjectType):
    class Meta:
        name = "TestCollectionsThingContainerMembers"
        model = models.ThingContainerMembers
        interfaces = (Collection,)


class MaybeHiddenThing(LibraryContentObjectType):
    class Meta:
        name = "TestCollectionsMaybeHiddenThing"
        model = models.MaybeHiddenThing


subschema = Subschema(
    types=[Thing, ThingContainer, ThingContainerMembers, MaybeHiddenThing]
)
