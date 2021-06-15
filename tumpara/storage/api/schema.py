import graphene
from graphene_django import DjangoConnectionField

from tumpara.api import Subschema

from . import Library
from .libraries import OrganizeLibraryContent


class Query(graphene.ObjectType):
    libraries = DjangoConnectionField(Library)


class Mutation(graphene.ObjectType):
    organize_library_content = OrganizeLibraryContent.Field()


subschema = Subschema(query=Query, mutation=Mutation)
