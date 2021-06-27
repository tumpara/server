import graphene
from django.db.models import QuerySet

from tumpara.api import Subschema
from tumpara.api.filtering import DjangoFilterSetConnectionField

from .. import models
from .albums import Album, CreateAlbum, UpdateAlbum
from .stacking import StackTimelineEntries, UnstackTimelineEntry
from .timeline_view import TimelineViewField


class Query(graphene.ObjectType):
    timeline = TimelineViewField(
        description="The complete timeline, as accessible by the currently logged in "
        "user."
    )
    timeline_albums = DjangoFilterSetConnectionField(Album)

    @staticmethod
    def resolve_timeline(root, info: graphene.ResolveInfo, **kwargs) -> QuerySet:
        return models.Entry.active_objects.stacks_for_user(info.context.user)

    @staticmethod
    def resolve_collections(root, info: graphene.ResolveInfo) -> QuerySet:
        return models.Album.objects.for_user(info.context.user)


class Mutation(graphene.ObjectType):
    stack_timeline_entries = StackTimelineEntries.Field()
    unstack_timeline_entry = UnstackTimelineEntry.Field()
    create_timeline_album = CreateAlbum.Field()
    update_timeline_album = UpdateAlbum.Field()


subschema = Subschema(query=Query, mutation=Mutation)
