import functools
from collections import OrderedDict, defaultdict
from typing import (
    ClassVar,
    Generator,
    Iterable,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import graphene
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import models as django_models
from django.forms.models import model_to_dict
from graphene import relay
from graphene.relay.node import from_global_id
from graphene_django import DjangoObjectType
from graphene_django.converter import convert_django_field_with_choices
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphene_django.registry import get_global_registry
from graphene_django.utils.utils import get_model_fields

from tumpara.accounts.models import GenericUser, MembershipHost
from tumpara.utils import pk_type

M = TypeVar("M")
I = TypeVar("I")

__all__ = [
    "resolve_global_id",
    "resolve_bulk_global_ids",
    "convert_model_field",
    "login_required",
    "CreateModelFormMutation",
    "UpdateModelFormMutation",
]


def _resolve_model(
    given_type: str,
    info: graphene.ResolveInfo,
    target_model: ClassVar[M] = django_models.Model,
    target_type: Optional[Type] = None,
):
    """Resolve a given schema type name into the corresponding model."""
    schema_type = info.schema.get_type(given_type)
    if schema_type is None:
        raise ValueError(
            f"The given node type {given_type!r} was not found in the schema."
        )
    schema_type = schema_type.graphene_type

    if (
        not issubclass(schema_type, DjangoObjectType)
        or relay.Node not in schema_type._meta.interfaces
    ):
        raise ValueError(
            f"The given object type {given_type!r} does not implement the Node "
            f"interface and therefore can't be looked up."
        )

    model = schema_type._meta.model

    if not issubclass(model, target_model):
        raise ValueError(
            f"The given node type {given_type!r} is of an invalid type for this "
            f"context."
            + (
                f" Expected an object of type {target_type.__name__}."
                if target_type
                else ""
            )
        )

    return model


def resolve_global_id(
    global_id: str,
    info: graphene.ResolveInfo,
    target_model: ClassVar[M] = django_models.Model,
    target_type: Optional[Type] = None,
    *,
    check_write_permissions: bool = False,
    permit_none: bool = False,
) -> M:
    """Resolve a given global ID (as output by graphene) into the corresponding
    Django model.

    The ID is a base64-encoded string of the format {Type}:{Key}, wherby the type is
    a GraphQL schema Node and the key is the primary key, whose type and format
    depends on the model.

    :param global_id: The global ID to lookup.
    :param info: Graphene request info.
    :param target_model: Parent class the model should have. If a global ID for a
        different model was given, a ValueError will be raised.
    :param target_type: Graphene type the object should have.
    :param check_write_permissions: If this is ``True`` and the user doesn't have
        writing permissions to the object, an exception will be raised.
    :param permit_none: Set this to False to return None instead of raising a
        ValueError when no object was found.
    :returns: The Django model found.
    :raises ValueError: When one of the following occurs, a ValueError is raised:
        - The given ID is an invalid base64 string
        - The given ID has an invalid syntax
        - The lookup resulted in a type that didn't match the given target type.
        - No object was found for the given ID
    :raises target_model.DoesNotExist: When the given ID does not point to an entry
        in the backend, the DoesNotExist error from the target type
    :raises PermissionDenied: When the object is visible, but not writeable.
    """

    def raise_permission():
        raise PermissionDenied(
            f"You do not have sufficient permissions to alter the "
            f"{target_type._meta.name + ' ' if target_type else ''} object with "
            f"id {global_id!r}."
        )

    if check_write_permissions:
        # Check for anonymous users before looking up anything so that non-logged-in
        # queries can't check if a given ID exists (and also doesn't hold up the
        # database).
        if not info.context.user.is_authenticated or not info.context.user.is_active:
            raise_permission()

    try:
        given_type, given_id = from_global_id(global_id)
    except Exception as e:
        raise ValueError(
            f"Unable to parse global ID {global_id!r}. Make sure it is a base64 "
            f'encoded string in the format "TypeName:id". Exception message: {str(e)}',
        )

    model = _resolve_model(given_type, info, target_model, target_type)

    try:
        obj = model.objects.get(pk=given_id)

        # Check visibility for library content objects.
        try:
            if not obj.check_visibility(
                info.context.user, writing=check_write_permissions
            ):
                raise ObjectDoesNotExist()
        except AttributeError:
            pass

        # Check memberships for membership hosts.
        try:
            if not obj.check_membership(
                info.context.user, ownership=True if check_write_permissions else None
            ):
                raise ObjectDoesNotExist()
        except AttributeError:
            pass

        return obj
    except ObjectDoesNotExist:
        if permit_none:
            return None
        raise model.DoesNotExist(
            f"Could not find the "
            f"{target_type._meta.name + ' ' if target_type else ''}object by id "
            f"{global_id!r}. Maybe you do not have sufficient permissions on the "
            f"object?"
        )


def resolve_bulk_global_ids(
    global_ids: Iterable[str],
    info: graphene.ResolveInfo,
    target_model: ClassVar[M] = django_models.Model,
    target_type: Optional[Type] = None,
    *,
    check_write_permissions: bool = False,
) -> Generator[Tuple[type(django_models.Model), Union[str, int]], None, None]:
    """Generator that will take a given set of global IDs and yield them grouped by
    the respective model type.

    This is useful as an alternative to :func:`resolve_global_id` when the object's
    primary keys will suffice for further processing. That way each model does not have
    to be instantiated, resulting in a database query.

    :param global_ids: The global IDs to lookup.
    :param info: Graphene request info.
    :param target_model: Parent class the model should have. If a global ID for a
        different model was given, a ValueError will be raised.
    :param target_type: Graphene type the object should have.
    :param target_type: Graphene type the object should have.
    :param check_write_permissions: If this is ``True`` and the user doesn't have
        writing permissions to the object, an exception will be raised.
    :returns: A generator that will yield tuples consisting of the model class and a
        list of primary keys. The order will be preserved for the model types. That
        means that models will be returned in the same order they were first seen in the
        input. Primary keys inside a model's tuple will be in the same order they were
        in given in.
    """

    def fail(global_id: Optional[str] = None):
        if global_id is None:
            raise Exception(
                f"Could not resolve the provided global IDs for the "
                f"{target_type._meta.name + ' ' if target_type else ''}objects. "
                f"Perhaps you have insufficient permissions?"
            )
        else:
            raise Exception(
                f"Could not resolve the provided global ID {global_id!r} for the "
                f"{target_type._meta.name + ' ' if target_type else ''}object. "
                f"Perhaps you have insufficient permissions?"
            )

    if check_write_permissions:
        # Check for anonymous users before looking up anything so that non-logged-in
        # queries can't check if a given ID exists (and also doesn't hold up the
        # database).
        if not info.context.user.is_authenticated or not info.context.user.is_active:
            fail()

    given_ids_by_type: Mapping[str, list] = OrderedDict()
    for global_id in global_ids:
        try:
            given_type, given_id = from_global_id(global_id)
        except Exception as e:
            raise ValueError(
                f"Unable to parse global ID {global_id!r}. Make sure it is a base64 "
                f'encoded string in the format "TypeName:id". Exception message: '
                f"{str(e)}",
            )

        if given_type not in given_ids_by_type:
            given_ids_by_type[given_type] = []
        given_ids_by_type[given_type].append(given_id)

    primary_keys_by_model: Mapping[
        type(django_models.Model), list[pk_type]
    ] = OrderedDict()
    for given_type, given_ids in given_ids_by_type.items():
        model = _resolve_model(given_type, info, target_model, target_type)

        if isinstance(model._meta.pk, django_models.IntegerField):
            # If the primary key is an integer, we can parse it accordingly.
            try:
                primary_keys = [int(pk) for pk in given_ids]
            except ValueError:
                raise ValueError(
                    "Unable to parse an ID. Make sure it has been provided exactly "
                    "as the API returned it."
                )
        else:
            primary_keys = given_ids

        # Check visibility for library content objects.
        try:
            if (
                model._default_manager.bulk_check_visibility(
                    info.context.user,
                    primary_keys,
                    writing=True if check_write_permissions else None,
                )
                is False
            ):
                fail()
        except AttributeError:
            pass

        # Check memberships for membership hosts.
        try:
            if (
                model._default_manager.bulk_check_membership(
                    info.context.user,
                    primary_keys,
                    ownership=True if check_write_permissions else None,
                )
                is False
            ):
                fail()
        except AttributeError:
            pass

        primary_keys_by_model[model] = primary_keys

    yield from primary_keys_by_model.items()


def convert_model_field(model, field_name: str) -> graphene.Field:
    """Convert a Django model's field into a Graphene field.."""
    registery = get_global_registry()
    for name, field in get_model_fields(model):
        if name == field_name:
            return convert_django_field_with_choices(field, registry=registery)
    raise KeyError(f"Could not find field {field_name!r} in model {model!r}.")


def login_required(fallback=None, error=False):
    """Decorator for resolvers that will fall back to a given value when the user is
    not logged in.

    :param fallback: The fallback value to return if the user is not logged in.
    """

    def decorator(function):
        @functools.wraps(function)
        def wrapper(root, info: graphene.ResolveInfo, *args, **kwargs):
            if (
                not info.context.user.is_authenticated
                or not info.context.user.is_active
            ):
                if callable(fallback):
                    return fallback()
                else:
                    return fallback
            return function(root, info, *args, **kwargs)

        return wrapper

    return decorator


class DisableIntrospectionMiddleware:
    """Graphene middleware that disables introspection queries."""

    def resolve(self, next, root, info, **args):
        # Disable access to all fields starting with '_'. This especially disables
        # the __schema and __type queries used for introspection. __typename is left
        # accessible because it may be used client-side to distinguish result types.
        if info.field_name.startswith("_") and info.field_name != "__typename":
            return None
        return next(root, info, **args)


class CreateModelFormMutation(DjangoModelFormMutation):
    """Graphene mutation for creating model instances using a ModelForm."""

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, exclude_fields=("id",), **options):
        if "id" not in exclude_fields:
            exclude_fields = ("id", *exclude_fields)

        return super().__init_subclass_with_meta__(
            exclude_fields=exclude_fields, **options
        )

    @classmethod
    def get_form_kwargs(cls, root, info: graphene.ResolveInfo, **input):
        user: GenericUser = info.context.user
        if not user.is_authenticated or not user.is_active:
            raise PermissionDenied("You do not have permission to create a new object.")

        # Explicitly don't check for existing objects here because we want to create a
        # new one.
        return {"data": input}

    @classmethod
    def mutate_and_get_payload(cls, root, info: graphene.ResolveInfo, **kwargs):
        result = super().mutate_and_get_payload(root, info, **kwargs)

        obj = getattr(result, cls._meta.return_field_name)

        if obj is None:
            return result

        if isinstance(obj, MembershipHost):
            obj.add_user(info.context.user, owner=True)

        return result


class UpdateModelFormMutation(DjangoModelFormMutation):
    """Graphene mutation for updating a model using a ModelForm.

    This will correctly resolve node IDs as well as check for permissions when mutating,
    when applicable. Also, this mutation supports partial updates and will use already
    present data as default values for the form.
    """

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, form_class=None, **options):
        if not form_class:
            raise Exception(
                "did not provide a 'form_class' option for the UpdateModelFormMutation"
            )

        class AugmentedUpdateForm(form_class):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault("use_required_attribute", False)
                super().__init__(*args, **kwargs)

                # This is necessary so that Graphene will not make the fields as
                # required (since we want to support partial updates).
                for field in self.fields.values():
                    field.required = False

        return super().__init_subclass_with_meta__(
            form_class=AugmentedUpdateForm, **options
        )

    @classmethod
    def get_form_kwargs(cls, root, info: graphene.ResolveInfo, **input):
        given_id = input.pop("id", None)
        output_type = cls._meta.fields[cls._meta.return_field_name].type
        instance = resolve_global_id(
            given_id,
            info,
            cls._meta.model,
            output_type,
            check_write_permissions=True,
        )

        data = model_to_dict(instance, cls._meta.form_class._meta.fields)
        data.update({key: value for key, value in input.items() if value is not None})

        return {"data": data, "instance": instance}
