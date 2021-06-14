from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.accounts.api import MembershipHost, User
from tumpara.api import Subschema

from . import models


class JoinableThing(DjangoObjectType):
    class Meta:
        name = "TestAccountsJoinableThing"
        model = models.JoinableThing
        interfaces = (relay.Node, MembershipHost)


subschema = Subschema(types=[JoinableThing])
