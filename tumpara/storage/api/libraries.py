from urllib.parse import urlparse

import graphene
from django import forms
from django.db import transaction
from django.db.models import QuerySet
from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.accounts.api import MembershipHost
from tumpara.api.util import (
    CreateModelFormMutation,
    UpdateModelFormMutation,
    convert_model_field,
    resolve_bulk_global_ids,
    resolve_global_id,
)

from .. import models


class LibrarySource(graphene.ObjectType):
    """Parsed source information for a library's backend."""

    scheme = graphene.String(
        required=True,
        description="The scheme string in source URI. This is used to determine the "
        "correct backend for the library.",
    )
    username = graphene.String()
    password = graphene.String()
    location = graphene.String()
    path = graphene.String()


class Library(DjangoObjectType):
    parsed_source = graphene.Field(
        LibrarySource,
        required=True,
        description="Information about the configured backend. This is parsed out of "
        "raw source string that has been configured.",
    )

    class Meta:
        model = models.Library
        interfaces = (relay.Node, MembershipHost)
        fields = ("context", "source")

    @classmethod
    def get_queryset(cls, queryset: QuerySet, info: graphene.ResolveInfo) -> QuerySet:
        return models.Library.objects.for_user(info.context.user, queryset=queryset)

    @staticmethod
    def resolve_parsed_source(library: models.Library, info: graphene.ResolveInfo):
        return urlparse(library.source)


class LibraryContentVisibility(graphene.Enum):
    PUBLIC = models.Visibility.PUBLIC
    INTERNAL = models.Visibility.INTERNAL
    MEMBERS = models.Visibility.MEMBERS
    OWNERS = models.Visibility.OWNERS
    UNSET = None

    @property
    def description(self):
        if self == LibraryContentVisibility.PUBLIC:
            return "Any caller may see the item (logged in or not)."
        elif self == LibraryContentVisibility.INTERNAL:
            return (
                "Only logged-in users may see the item. No further testing is "
                "performed - anyone with an account may see it. "
            )
        elif self == LibraryContentVisibility.MEMBERS:
            return (
                "Members of the library that the item belongs too are allowed to "
                "see it. "
            )
        elif self == LibraryContentVisibility.OWNERS:
            return (
                "Only members which are also owner of the library that the item "
                "belongs too are allowed to see it. "
            )
        elif self is None:
            return "Infer the visibility from the library's default setting."


class LibraryContent(relay.Node):
    library = convert_model_field(models.LibraryContent, "library")
    visibility = LibraryContentVisibility(
        required=True, description=models.LibraryContent.library.field.help_text
    )

    @classmethod
    def resolve_visibility(cls, obj: models.LibraryContent, info: graphene.ResolveInfo):
        return obj.actual_visibility


class LibraryCreateForm(forms.ModelForm):
    class Meta:
        model = models.Library
        fields = ("context", "source")


class CreateLibrary(CreateModelFormMutation):
    """Add a new library."""

    class Meta:
        form_class = LibraryCreateForm


class LibraryUpdateForm(forms.ModelForm):
    class Meta:
        model = models.Library
        fields = ("source",)


class UpdateLibrary(UpdateModelFormMutation):
    """Update fields of an existing library. Note that the context cannot be updated."""

    class Meta:
        form_class = LibraryUpdateForm


class OrganizeLibraryContent(relay.ClientIDMutation):
    """Set visibility for library content."""

    class Input:
        ids = graphene.List(
            graphene.ID,
            description="List of nodes (identified by their ID) to update.",
        )

        visibility = LibraryContentVisibility(
            description="The new visibility value to be set."
        )

    nodes = graphene.List(
        LibraryContent, required=True, description="The set of all updated nodes."
    )

    @classmethod
    @transaction.atomic
    def mutate(cls, root, info: graphene.ResolveInfo, input: Input):
        for model, primary_keys in resolve_bulk_global_ids(
            input.ids,
            info,
            models.LibraryContent,
            LibraryContent,
            check_write_permissions=True,
        ):
            model._default_manager.bulk_set_visibility(primary_keys, input.visibility)

        return {
            "nodes": (
                resolve_global_id(
                    given_id,
                    info,
                    models.LibraryContent,
                    LibraryContent,
                )
                for given_id in input.ids
            )
        }
