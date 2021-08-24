import graphene
from django import forms
from django.db.models import Q, QuerySet
from graphene import relay

from tumpara.accounts.api import MembershipHostObjectType
from tumpara.api.filtering import (
    DjangoFilterSetConnectionField,
    FilteredDjangoObjectType,
)
from tumpara.api.util import CreateModelFormMutation, UpdateModelFormMutation
from tumpara.collections.api import ArchivableFilterSet, Collection

from .. import models


class AlbumFilterSet(ArchivableFilterSet):
    """Filters for looking up timeline albums."""

    search = graphene.String(description="Search string to filter users.")

    class Meta:
        name = "TimelineAlbumFilterSet"

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        query = super().build_query(info, prefix)

        if self.search:
            query &= Q(**{f"{prefix}name__icontains": self.search})

        return query


class Album(FilteredDjangoObjectType, MembershipHostObjectType):
    class Meta:
        name = "TimelineAlbum"
        model = models.Album
        interfaces = (Collection,)
        filter_set = AlbumFilterSet


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
