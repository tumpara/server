import graphene
from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from tumpara.api import Subschema
from tumpara.api.filtering import DjangoFilterSetConnectionField
from tumpara.api.util import login_required

from .. import models
from . import User
from .types import RemoveMembership, SetMembership


class Query(graphene.ObjectType):
    me = graphene.Field(
        User,
        description="The currently logged in user, if any. This field will be null for "
        "anonymous sessions.",
    )
    users = DjangoFilterSetConnectionField(User)

    @staticmethod
    @login_required(fallback=None)
    def resolve_me(root, info: graphene.ResolveInfo) -> AbstractUser:
        return info.context.user

    @staticmethod
    @login_required(fallback=models.User.objects.none)
    def resolve_users(root, info: graphene.ResolveInfo, *args, **kwargs) -> QuerySet:
        return models.User.objects.all()


class Mutation(graphene.ObjectType):
    set_membership = SetMembership.Field()
    remove_membership = RemoveMembership.Field()


subschema = Subschema(query=Query, mutation=Mutation)
