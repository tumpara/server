import graphene
from django import forms
from django.db.models import Q, QuerySet
from graphene import relay

from tumpara.accounts.api import MembershipHost
from tumpara.api.filtering import (
    DjangoFilterSetConnectionField,
    FilteredDjangoObjectType,
)
from tumpara.api.util import CreateModelFormMutation, UpdateModelFormMutation
from tumpara.collections.api import ArchivableFilterSet, Collection

from .. import models


class AlbumFilterSet(ArchivableFilterSet):
    """Filters for looking up timeline albums."""

    class Meta:
        name = "TimelineAlbumFilterSet"


class Album(FilteredDjangoObjectType):
    children = DjangoFilterSetConnectionField(
        lambda: Album,
        filter_set_type=AlbumFilterSet,
        description="Sub-albums that have this one as a parent. Note this only goes"
        "one level deep.",
    )

    class Meta:
        name = "TimelineAlbum"
        model = models.Album
        interfaces = (relay.Node, Collection, MembershipHost)
        filter_set = AlbumFilterSet

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        return models.Album.objects.for_user(
            info.context.user, queryset=queryset, ownership=True if writing else None
        )


class AlbumForm(forms.ModelForm):
    class Meta:
        model = models.Album
        fields = ("name", "archived")


class CreateAlbum(CreateModelFormMutation):
    """Create a new timeline album."""

    class Meta:
        name = "CreateTimelineAlbum"
        form_class = AlbumForm


class UpdateAlbum(UpdateModelFormMutation):
    """Update fields of an existing timeline album."""

    class Meta:
        name = "UpdateTimelineAlbum"
        form_class = AlbumForm
