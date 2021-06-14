import graphene

from tumpara.api import Subschema

from .archiving import OrganizeArchive
from .collections import OrganizeCollection


class Mutation(graphene.ObjectType):
    organize_collection = OrganizeCollection.Field()
    organize_archive = OrganizeArchive.Field()


subschema = Subschema(mutation=Mutation)
