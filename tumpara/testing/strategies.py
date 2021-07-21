import os
import shutil
import tempfile
from functools import partial

import hypothesis.strategies
from hypothesis import assume
from hypothesis.control import cleanup
from hypothesis.extra.django import from_field, from_form, from_model  # noqa
from hypothesis.strategies import *

from tumpara.accounts.models import User

__all__ = (
    hypothesis.strategies.__all__
    + ["from_field", "from_form", "from_model"]
    + [
        "temporary_directories",
        "directory_names",
        "filenames",
        "directory_trees",
        "superusers",
        "from_unique_model",
    ]
)

from typing import Any, List, Tuple


@composite
def temporary_directories(draw: DataObject.draw) -> SearchStrategy[str]:
    """Hypothesis strategy that creates temporary directories."""
    directory = tempfile.mkdtemp()

    @cleanup
    def teardown_temporary_directory():
        shutil.rmtree(directory)

    return directory


@composite
def directory_names(draw: DataObject.draw, exclude=[]) -> SearchStrategy[str]:
    """Hypothesis strategy that generates valid directory names, optionally excluding
    a list of already generated names.
    """
    result = draw(from_regex(r"[a-zA-Z][a-zA-Z\ \-_\.0-9]*", fullmatch=True))
    assume(result not in exclude)
    return result


@composite
def filenames(draw: DataObject.draw, exclude=[]) -> SearchStrategy[str]:
    """Hypothesis strategy that generates valid filenames with an extension, optionally
    excluding a list of already generated names.
    """
    exclude = map(os.path.basename, exclude)
    result = draw(
        from_regex(r"[a-zA-Z0-9][a-zA-Z\ \-_0-9]*\.[a-z0-9]{1,4}", fullmatch=True)
    )
    assume(result not in exclude)
    return result


@composite
def directory_trees(
    draw: DataObject.draw,
) -> SearchStrategy[tuple[list[str], list[str], list[Any]]]:
    """Hypothesis strategy that generates a random directory tree.

    The tree returned consists of a list of folders, a list of files and a list of
    file contents. Files are distributed among the folders randomly. This strategy
    only yields the structure of the resulting filesystem - no files are actually
    created.
    """
    folders = [""]
    # Create up to 20 additional directories, each underneath one of the existing
    # directories.
    for _ in range(draw(integers(1, 4))):
        base = draw(sampled_from(folders))
        name = draw(directory_names())
        path = os.path.join(base, name)
        assume(path not in folders)
        folders.append(path)

    file_paths = []
    file_contents = []
    # Create a random number of files in those folders and populate them with random
    # text.
    for _ in range(draw(integers(2, 15))):
        directory = draw(sampled_from(folders))
        name = draw(filenames())
        path = os.path.join(directory, name)
        assume(path not in file_paths)
        file_paths.append(path)
        file_contents.append(draw(text(min_size=1)))

    return folders, file_paths, file_contents


users = partial(
    from_model,
    User,
    is_active=just(True),
    is_staff=just(False),
    is_superuser=just(False),
)
superusers = partial(
    from_model, User, is_active=just(True), is_staff=just(True), is_superuser=just(True)
)


optional_booleans = partial(sampled_from, [None, True, False])

# GraphQL Ints may only be signed 32 bit.
graphql_ints = partial(integers, min_value=-(2 ** 31) + 1, max_value=2 ** 31 - 1)

# Values for the 'prefix' parameter of filters and filter sets.
field_prefix = partial(from_regex, f"^[a-z0-9]+(__?[a-z0-9]+)")
