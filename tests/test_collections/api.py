import graphene
from django.db.models import QuerySet
from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.accounts.api import MembershipHost
from tumpara.accounts.models import GenericUser
from tumpara.api import Subschema
from tumpara.collections.api import Archivable, ArchivableFilterSet, Collection

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


class ThingContainerMembers(DjangoObjectType):
    class Meta:
        name = "TestCollectionsThingContainerMembers"
        model = models.ThingContainerMembers
        interfaces = (relay.Node, Collection, MembershipHost)

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        return models.ThingContainerMembers.objects.for_user(
            info.context.user, queryset=queryset, ownership=True if writing else None
        )


class MaybeHiddenThing(DjangoObjectType):
    class Meta:
        name = "TestCollectionsMaybeHiddenThing"
        model = models.MaybeHiddenThing
        interfaces = (relay.Node,)

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        return models.MaybeHiddenThing.objects.for_user(
            info.context.user, queryset=queryset, writing=writing
        )


subschema = Subschema(
    types=[Thing, ThingContainer, ThingContainerMembers, MaybeHiddenThing]
)
