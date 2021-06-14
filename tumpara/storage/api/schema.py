import graphene
from graphene_django import DjangoConnectionField

from tumpara.api import Subschema

from . import Library
from .libraries import OrganizeLibraryContent


class Query(graphene.ObjectType):
    libraries = DjangoConnectionField(
        Library,
        owner=graphene.Boolean(
            description="Ownership state the user should have. If this is null, "
            "all libraries related to the currently logged in user will be returned. "
            "If it is true or false, only libraries where the current user is or is "
            "not an owner will be returned."
        ),
    )


class Mutation(graphene.ObjectType):
    organize_library_content = OrganizeLibraryContent.Field()


subschema = Subschema(query=Query, mutation=Mutation)
