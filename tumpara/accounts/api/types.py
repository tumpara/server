from typing import Optional

import graphene
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.api.filtering import FilteredDjangoObjectType, FilterSet
from tumpara.api.util import login_required, resolve_global_id

from .. import models


class MembershipInfo(DjangoObjectType):
    """Information about the relationship of a membership subject (like a user) and a
    host."""

    class Meta:
        model = models.UserMembership
        fields = ("is_owner",)


class UserFilterSet(FilterSet):
    """Filters for looking up users."""

    search = graphene.String(description="Search string to filter users.")

    def build_query(self, info: graphene.ResolveInfo, prefix: str = "") -> Q:
        query = Q()

        if self.search:
            query &= (
                Q(**{f"{prefix}username__icontains": self.search})
                | Q(**{f"{prefix}first_name__icontains": self.search})
                | Q(**{f"{prefix}last_name__icontains": self.search})
            )

        return query


class User(FilteredDjangoObjectType):
    email = graphene.String(
        description="The user's email. This can only be read by the user themself."
    )
    membership_info = graphene.Field(
        MembershipInfo,
        description="Information about this user's membership in a given host. If "
        "this is null, then the user is not a member.",
        host_id=graphene.ID(required=True),
    )

    class Meta:
        model = models.User
        interfaces = (relay.Node,)
        fields = ("username", "first_name", "last_name")
        filter_set = UserFilterSet

    @classmethod
    def get_queryset(
        cls, queryset: QuerySet, info: graphene.ResolveInfo, *, writing: bool = False
    ) -> QuerySet:
        user: models.GenericUser = info.context.user
        if not user.is_authenticated or not user.is_active:
            return queryset.none()
        if writing and not user.is_superuser:
            queryset = queryset.filter(pk=user.pk)
        return queryset

    @staticmethod
    @login_required()
    def resolve_email(target: models.User, info: graphene.ResolveInfo) -> Optional[str]:
        user: models.User = info.context.user
        if user == target or user.is_superuser:
            return target.email
        return None

    @staticmethod
    @login_required()
    def resolve_membership_info(
        target: models.User, info: graphene.ResolveInfo, host_id
    ) -> Optional[models.UserMembership]:
        host: models.MembershipHost = resolve_global_id(
            host_id, info, models.MembershipHost, MembershipHost
        )
        return host.get_membership_for_user(target, requester=info.context.user)


class UserMembershipConnection(relay.Connection):
    class Meta:
        node = User

    class Edge:
        info = graphene.Field(
            MembershipInfo, required=True, description="Details on this membership"
        )

        @staticmethod
        def resolve_node(edge, info: graphene.ResolveInfo) -> models.User:
            return edge.node.user

        @staticmethod
        def resolve_info(edge, info: graphene.ResolveInfo) -> models.UserMembership:
            return edge.node


class MembershipHost(relay.Node):
    """Types implementing this interface can contain members - users may be added
    either as a normal member or as an owner with edit permissions.
    """

    member_users = relay.ConnectionField(
        UserMembershipConnection,
        description="All users that are a member of this container.",
        ownership_filter=graphene.Boolean(
            description="Used to specifically filter memberships depending on whether "
            "the user is an owner or not. Set this to true to only return owners, "
            "set it to false to only return non-owners. A value of null performs no "
            "filtering."
        ),
    )

    @staticmethod
    def resolve_member_users(
        obj: models.MembershipHost,
        info: graphene.ResolveInfo,
        ownership_filter: Optional[bool] = None,
        **kwargs,
    ):
        return obj.all_user_memberships(requester=info.context.user)


class MembershipMutation(relay.ClientIDMutation):
    class Input:
        host_id = graphene.ID(
            required=True,
            description="ID of the membership host. This must be something "
            "implementing MembershipHost.",
        )
        subject_id = graphene.ID(
            required=True, description="ID of the member. This should be a User."
        )

    host = graphene.Field(MembershipHost, description="The updated membership host.")

    class Meta:
        abstract = True

    @classmethod
    def _handle_user(
        cls,
        info: graphene.ResolveInfo,
        host: models.MembershipHost,
        subject: models.User,
        input: Input,
    ):
        raise NotImplementedError

    @classmethod
    def mutate(cls, root, info: graphene.ResolveInfo, input: Input):
        host: models.MembershipHost = resolve_global_id(
            input.host_id,
            info,
            models.MembershipHost,
            MembershipHost,
        )
        # We don't use the type checking from resolve_global_id here because we might
        # add more subject types in the future.
        subject = resolve_global_id(input.subject_id, info)

        if isinstance(subject, models.User):
            cls._handle_user(info, host, subject, input)
        else:
            raise TypeError(
                "The given subject ID does not have the correct type. It must be a "
                "User."
            )

        return {"host": host}


class SetMembership(MembershipMutation):
    """Edit the membership of something to a membership host. This mutation can
    create or update memberships."""

    class Input(MembershipMutation.Input):
        owner = graphene.Boolean(
            default=False, description="Whether the member is an owner."
        )

    @classmethod
    def _handle_user(
        cls,
        info: graphene.ResolveInfo,
        host: models.MembershipHost,
        subject: models.User,
        input: Input,
    ):
        host.add_user(subject, input.owner, requester=info.context.user)


class RemoveMembership(MembershipMutation):
    """Remove a membership from a given host."""

    @classmethod
    def _handle_user(
        cls,
        info: graphene.ResolveInfo,
        host: models.MembershipHost,
        subject: models.User,
        input: MembershipMutation.Input,
    ):
        host.remove_user(subject, requester=info.context.user)
