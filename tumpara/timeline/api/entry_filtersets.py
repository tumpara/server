from typing import Type

from tumpara.api.filtering import FilterSet

entry_filtersets: dict[str, tuple[str, Type[FilterSet]]] = {}


def entry_type_filterset(graphql_type_name, model_properties):
    """Register a filterset class for an entry type.

    This should be used as a decorator on a :class:`FilterSet` subclass. Note that
    the filterset will be evaluated on Entry objects (not their concrete
    implementations), so any fields in a subtype must be prefixed accordingly.
    Example: instead of returning a query like `Q(numberfield=7)` it needs to be
    prefixed like `Q(myentrytype__numberfield=7)`. In most cases, the prefix eqauls
    the value of the `property_name` parameter passed here.

    :param graphql_type_name: Full name of the entry's GraphQL type, as it is shown
        in the API.
    :param model_properties: Property name on the base Entry model where the subtype can
        be accessed. This will also be used to prefix the field in the API. If this is
        an iterable, they will be OR-ed together - which is useful when unifying
        multiple backend models into a single API type.
    """
    if isinstance(model_properties, str):
        model_properties = (model_properties,)

    def decorator(filterset_class):
        assert issubclass(
            filterset_class, FilterSet
        ), "entry type filter must be a subclass of 'EntryTypeFilterSet'"

        entry_filtersets[graphql_type_name] = (model_properties, filterset_class)
        return filterset_class

    return decorator
