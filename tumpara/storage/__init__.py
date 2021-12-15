from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable, MutableMapping, MutableSequence, Type

if TYPE_CHECKING:
    from .backends.base import LibraryBackend
    from .models import FileHandler


# Mapping from schemas to storage backends.
library_backends: MutableMapping[str, Type[LibraryBackend]] = {}

# This dictionary stores all registered file handlers. It's keys are known
# possibilities for a library's `context` field and the corresponding values are
# lists of file handlers.
file_handlers: MutableMapping[str, MutableSequence[Type[FileHandler]]] = {}


def register_library_backend(
    scheme: str,
) -> Callable[[Type[LibraryBackend]], Type[LibraryBackend]]:
    """Decorator to register the given class as a library backend.

    :param scheme: URI scheme this backend is responsible for.
    """
    from .backends.base import LibraryBackend

    assert (
        isinstance(scheme, str) and len(scheme) > 0
    ), "No scheme provided for registering library backend."
    assert re.search(
        r"^[a-zA-Z]([a-zA-Z0-9$\-_@.&!*\"'(),]|%[0-9a-fA-F]{2})*$", scheme
    ), f"Library backend scheme {scheme!r} contains invalid characters."

    def decorator(backend_class: Type[LibraryBackend]) -> Type[LibraryBackend]:
        assert issubclass(
            backend_class, LibraryBackend
        ), "Library backends must be a subclass of LibraryBackend."

        if scheme in library_backends:
            raise RuntimeError(
                f"Trying to register more than one library backend for scheme "
                f"{scheme!r}."
            )

        library_backends[scheme] = backend_class

        return backend_class

    return decorator


def register_file_handler(
    library_context: str,
) -> Callable[[Type[FileHandler]], Type[FileHandler]]:
    """Decorator to register the given class as a file handler.

    :param library_context: The context this handler should be place in. It will be
        active for libraries with the same `context` set.
    """
    from .models import FileHandler

    assert (
        isinstance(library_context, str) and len(library_context) > 0
    ), "No library context was provided when registering the file handler."

    def decorator(handler_class: Type[FileHandler]) -> Type[FileHandler]:
        assert issubclass(
            handler_class, FileHandler
        ), "File handlers must be a subclass of FileHandler."

        if library_context not in file_handlers:
            file_handlers[library_context] = []
        file_handlers[library_context].append(handler_class)

        return handler_class

    return decorator
