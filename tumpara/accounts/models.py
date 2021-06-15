from __future__ import annotations

from typing import Iterable, Optional, Union

from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from tumpara.utils import map_object_to_primary_key, pk_type

__all__ = [
    "AnonymousUser",
    "GenericUser",
    "User",
    "UserMembership",
    "MembershipHostManager",
    "MembershipHost",
]


GenericUser = Union[AbstractUser, AnonymousUser]


class User(AbstractUser):
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")


class AbstractMembership(models.Model):
    is_owner = models.BooleanField(
        verbose_name=_("owner status"),
        help_text=_(
            "Designates that this membership has edit permissions on the object (for "
            "containers, they may add or remove)."
        ),
    )

    class Meta:
        abstract = True


class UserMembership(AbstractMembership):
    """Membership of a user in an object of type :class:`MembershipHost`."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships",
        related_query_name="membership",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = _("user membership")
        verbose_name_plural = _("user memberships")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="user_object_membership_unique",
            ),
        ]


class MembershipHostManager(models.Manager):
    def for_user(
        self,
        user: User,
        *,
        ownership: Optional[bool] = None,
        queryset: Optional[QuerySet] = None,
    ) -> QuerySet:
        """Filter all objects where a given user is member.

        This does not include any objects that may proxy their membership using the
        :func:`MembershipHost.actual_host` property.

        :param user: The user that is logged in. This will determine the scope of
            permissions.
        :param ownership: Optional ownership filter. If this is True (False),
            only objects where the given user is (is not) an owner will be returned. If
            this is None, no filtering is performed.
        :param queryset: Use this to filter an existing queryset instead of the
            entire database.
        """
        if queryset is None:
            queryset = self.get_queryset()

        if not user.is_authenticated or not user.is_active:
            return queryset.none()
        elif user.is_superuser:
            return queryset
        else:
            query = Q(user_memberships__user=user)
            if ownership is not None:
                query &= Q(user_memberships__is_owner=ownership)
            return queryset.filter(query)

    def owned_by(self, user: User) -> QuerySet:
        """Filter all objects where a given user is owner.

        :param user: The user that is logged in. This will determine the scope of
            permissions.
        """
        return self.for_user(user, ownership=True)

    def bulk_check_membership(
        self,
        user: GenericUser,
        objects: Iterable[Union[models.Model, pk_type]],
        *,
        ownership: Optional[bool] = None,
    ):
        """Check whether a given user is member in all of the provided objects.

        :param user: The user in question.
        :param objects: The objects that the user should be a member of.
        :param ownership: If this is not ``None``, ``True`` will only be returned
            if the memberships have the ownership field set accordingly. To succeed only
            for owners, set this to ``True``.
        :returns: A boolean, showing whether the provided user is a member in all of the
            provided objects. If a given object does not exist, ``False`` will be
            returned.
        """
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser and user.is_active:
            return True

        pks: list[pk_type] = [
            map_object_to_primary_key(item, self.model, "bulk membership checking")
            for item in objects
        ]

        query = Q(pk__in=pks, user_memberships__user=user)
        if ownership is not None:
            query &= Q(user_memberships__is_owner=ownership)
        return self.filter(query).count() == len(pks)


class MembershipHost(models.Model):
    """Base class of objects where users may be 'members'.

    For example libraries use the membership model to filter out which user is
    allowed to access them. But memberships can also be used to model 'sharing' of
    objects with other users (as in sharing a collection with another user so they
    can view it).
    """

    user_memberships = GenericRelation(UserMembership)

    objects = MembershipHostManager()

    class Meta:
        abstract = True

    def add_user(
        self, user: User, owner: bool = False, *, requester: GenericUser = None
    ):
        """Add a given user. This will create a membership for them, if it does not
        exit yet.

        :param user: The user to add.
        :param owner: Whether the user should be an owner.
        :param requester: If provided, the operation will only be performed if this user
            is an owner. Otherwise a PermissionDenied exception will be raised.
        """
        if not user.is_authenticated or not user.is_active:
            raise ValueError(
                "Cannot add an anonymous or inactive user to a membership."
            )
        membership = self.get_membership_for_user(user, requester=requester)
        if membership is None:
            self.user_memberships.create(user=user, is_owner=owner)
        else:
            membership.is_owner = owner
            membership.save()

    def remove_user(self, user: User, *, requester: GenericUser = None):
        """Remove a given user's membership.

        :param user: The user to remove.
        :param requester: If provided, the operation will only be performed if this user
            is an owner. Otherwise a PermissionDenied exception will be raised.
        """
        if requester is not None and requester != user and not self.is_owner(requester):
            raise PermissionDenied(
                "The requesting user does not have permission to delete memberships on "
                f"this {self.__class__.__name__}."
            )
        self.user_memberships.filter(user=user).delete()

    def check_membership(self, user: GenericUser, *, ownership: Optional[bool] = None):
        """Check whether a given user is a member.

        :param user: The user in question.
        :param ownership: If this is not ``None``, ``True`` will only be returned
            if the membership has the ownership field set accordingly. To succeed only
            for owners, set this to ``True``.
        """
        if not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser and user.is_active:
            return True

        query = Q(user=user)
        if ownership is not None:
            query &= Q(is_owner=ownership)
        return self.user_memberships.filter(query).exists()

    def is_member(self, *args, **kwargs):
        """Check whether a given user is a member (owner or not)."""
        return self.check_membership(*args, ownership=None, **kwargs)

    def is_owner(self, *args, **kwargs):
        """Check whether a given user is an owner."""
        return self.check_membership(*args, ownership=True, **kwargs)

    def get_membership_for_user(
        self, user: GenericUser, *, requester: GenericUser = None
    ) -> Optional[AbstractMembership]:
        """Get the highest ranking membership for a user.

        :param user: The use to check membership for.
        :param requester: If provided, a result will only be returned if this user is
            an owner. Otherwise a PermissionDenied exception will be raised.
        """
        if requester is not None and not self.is_owner(requester):
            raise PermissionDenied(
                "The requesting user does not have permission to check or modify "
                f"memberships on this {self.__class__.__name__}."
            )

        if not user.is_authenticated or not user.is_active:
            return None
        try:
            return self.user_memberships.get(user=user)
        except UserMembership.DoesNotExist:
            return None

    def clear_memberships(self):
        """Remove all memberships."""
        self.user_memberships.delete()

    def all_user_memberships(self, *, requester: GenericUser = None) -> QuerySet:
        """Build a QuerySet for all user memberships.

        :param requester: If provided, a result will only be returned if this user is
            an owner. Otherwise a PermissionDenied exception will be raised.
        """
        if requester is not None and not self.is_owner(requester):
            raise PermissionDenied(
                "The requesting user does not have permission to fetch memberships on "
                f"this {self.__class__.__name__}."
            )
        return self.user_memberships.all()
