from typing import Mapping, Tuple, Type

from tumpara.api.filtering import FilterSet

entry_filtersets: Mapping[str, Tuple[str, Type[FilterSet]]] = {}


def entry_type_filterset(graphql_type_name, property_name):
    """Register a filterset class for an entry type.

    This should be used as a decorator on a :class:`FilterSet` subclass. Note that
    the filterset will be evaluated on Entry objects (not their concrete
    implementations), so any fields in a subtype must be prefixed accordingly.
    Example: instead of returning a query like `Q(numberfield=7)` it needs to be
    prefixed like `Q(myentrytype__numberfield=7)`. In most cases, the prefix eqauls
    the value of the `property_name` parameter passed here.

    :param graphql_type_name: Full name of the entry's GraphQL type, as it is shown
        in the API.
    :param property_name: Property name on the base Entry model where the subtype can
        be accessed. This will also be used to prefix the field in the API.
    """

    def decorator(filterset_class):
        assert issubclass(
            filterset_class, FilterSet
        ), "entry type filter must be a subclass of 'EntryTypeFilterSet'"
        entry_filtersets[graphql_type_name] = (property_name, filterset_class)
        return filterset_class

    return decorator
