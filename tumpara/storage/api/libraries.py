from typing import Optional
from urllib.parse import urlparse

import graphene
from django import forms
from django.db import transaction
from django.db.models import Q, QuerySet
from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.accounts.api import MembershipHostObjectType
from tumpara.api.filtering import FilterSet
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


class Library(MembershipHostObjectType):
    parsed_source = graphene.Field(
        LibrarySource,
        required=True,
        description="Information about the configured backend. This is parsed out of "
        "raw source string that has been configured.",
    )

    class Meta:
        model = models.Library
        fields = ("context", "source")

    @staticmethod
    def resolve_parsed_source(library: models.Library, info: graphene.ResolveInfo):
        return urlparse(library.source)


class LibraryContentVisibility(graphene.Enum):
    PUBLIC = models.Visibility.PUBLIC
    INTERNAL = models.Visibility.INTERNAL
    MEMBERS = models.Visibility.MEMBERS
    OWNERS = models.Visibility.OWNERS

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


class LibraryContent(relay.Node):
    library = convert_model_field(models.LibraryContent, "library")
    given_visibility = LibraryContentVisibility(
        description=models.LibraryContent.visibility.field.help_text
        + "This is the value that was has been set - if this is null, the effective "
        "visiblity will be inherited from the library."
    )
    effective_visibility = LibraryContentVisibility(
        required=True,
        description="The actually active visibility value, which may be inferred from "
        "the library.",
    )

    @classmethod
    def resolve_given_visibility(
        cls, obj: models.LibraryContent, info: graphene.ResolveInfo
    ):
        return obj.visibility

    @classmethod
    def resolve_effective_visibility(
        cls, obj: models.LibraryContent, info: graphene.ResolveInfo
    ):
        return obj.effective_visibility


class LibraryContentObjectType(DjangoObjectType):
    """Django object type for library content models that will correctly handle the
    right GraphQL interfaces as well as the permissions in the queryset lookup.
    """

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(
        cls, model=None, interfaces=(), exclude=(), **options
    ):
        assert issubclass(model, models.LibraryContent), (
            f"Cannot create a library content API type because the provided model "
            f"{model!r} is not a LibraryContent model. "
        )

        if LibraryContent not in interfaces:
            interfaces = (LibraryContent, *interfaces)
        if relay.Node not in interfaces:
            interfaces = (relay.Node, *interfaces)

        # Visibility is handled by the interface above.
        if "visibility" not in exclude:
            exclude = ("visibility", *exclude)

        super().__init_subclass_with_meta__(
            model=model, interfaces=interfaces, exclude=exclude, **options
        )

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        return cls._meta.model.objects.for_user(
            info.context.user, queryset=queryset, writing=True
        )


class LibraryContentFilterSet(FilterSet):
    effective_visibility: Optional[list[Optional[int]]] = graphene.List(
        LibraryContentVisibility,
        description="Visibility settings results should have. If this option is not "
        "given, no filtering will be performed. If it is, only items that are "
        "visible corresponding to one of provided options will be returned (either "
        "directly or indirectly via their library's default setting).",
    )

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        query = super().build_query(info, prefix)

        if self.effective_visibility is not None:
            query &= Q(
                **{
                    f"{prefix}effective_visibility__in": (
                        option
                        for option in self.effective_visibility
                        if option is not None
                    )
                }
            )

        return query

    def prepare_queryset(self, queryset: QuerySet, prefix: str = "") -> QuerySet:
        queryset = super().prepare_queryset(queryset, prefix)
        if not isinstance(
            queryset.model._meta.default_manager, models.LibraryContentManager
        ):
            raise ValueError(
                f"The queryset passed to a library content filter set must have a "
                f"LibraryContentManager as the default manager (got "
                f"{queryset.model._meta.default_manager!r})."
            )
        queryset = queryset.model._meta.default_manager.with_effective_visibility(
            queryset, prefix=prefix
        )
        return queryset


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
            required=True,
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
