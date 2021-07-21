import os
from functools import partial
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from hypothesis import HealthCheck, given, settings
from hypothesis.control import cleanup

from tumpara.storage import scanner
from tumpara.storage.backends import *
from tumpara.storage.scanner import events
from tumpara.testing import strategies as st

filesystem_backend_context = tuple[str, list[str], list[str], FileSystemBackend]
filesystem_backend_watch_context = tuple[
    str, list[str], list[str], FileSystemBackend, scanner.EventGenerator
]


@st.composite
def filesystem_backend_contexts(draw) -> st.SearchStrategy[filesystem_backend_context]:
    library_base = draw(st.temporary_directories())
    folders, file_paths, file_contents = draw(st.directory_trees())

    for path in folders[1:]:
        os.mkdir(os.path.join(library_base, path))
    for i in range(len(file_paths)):
        with open(os.path.join(library_base, file_paths[i]), "w") as f:
            f.write(file_contents[i])

    backend = FileSystemBackend(urlparse(f"file://{library_base}"))
    return library_base, folders, file_paths, backend


@st.composite
def filesystem_backend_watch_contexts(
    draw,
) -> st.SearchStrategy[filesystem_backend_watch_context]:
    library_base, folders, file_paths, backend = draw(filesystem_backend_contexts())
    generator = backend.watch()

    @cleanup
    def teardown_backend_watch():
        try:
            generator.send(False)
        except (StopIteration, TypeError):
            pass

    return library_base, folders, file_paths, backend, generator


FILESYSTEM_BACKEND_SETTINGS = {
    "max_examples": 15,
    "suppress_health_check": (HealthCheck.too_slow, HealthCheck.data_too_large),
}


class FileSystemBackendTests(SimpleTestCase):
    """Test cases for the file system backend.

    Only the functionality provided by the backend is tested here, everything that
    comes from Django's storage API is ignored.
    """

    @settings(max_examples=1)
    @given(st.temporary_directories())
    def test_check(self, library_base: str):
        """Backend raises errors when an invalid path is specified."""

        try:
            FileSystemBackend(urlparse(f"file://{library_base}")).check()
        except ValidationError:
            self.fail("Backend raised ValidationError on valid input.")

        self.assertRaisesRegex(
            ValidationError,
            r"does not exist",
            lambda: FileSystemBackend(
                urlparse(f"file://{library_base}/invalid")
            ).check(),
        )

        with open(f"{library_base}/file", "w") as f:
            f.write("Hello")
        self.assertRaisesRegex(
            ValidationError,
            r"is not a directory",
            lambda: FileSystemBackend(urlparse(f"file://{library_base}/file")).check(),
        )

    @settings(**FILESYSTEM_BACKEND_SETTINGS)
    @given(filesystem_backend_contexts())
    def test_walk_files(self, context: filesystem_backend_context):
        library_base, _, files, backend = context
        paths = list(backend.walk_files())

        paths_set = set(paths)
        files_set = set(files)
        self.assertEqual(paths_set, files_set)

    @settings(**FILESYSTEM_BACKEND_SETTINGS)
    @given(filesystem_backend_watch_contexts(), st.data())
    def test_watch_file_edits(self, context: filesystem_backend_watch_context, data):
        """Events emitted from file edits are the correct FileModifiedEvent objects."""
        library_base, folders, files, backend, generator = context

        for path in data.draw(st.sets(st.sampled_from(files), min_size=2, max_size=6)):
            with open(os.path.join(library_base, path), "a") as f:
                f.write(data.draw(st.text(min_size=10)))
            event = next(generator)
            self.assertIsInstance(event, events.FileModifiedEvent)
            self.assertEqual(event.path, path)

        self.assertIs(generator.send("check_empty"), True)

    @settings(**FILESYSTEM_BACKEND_SETTINGS)
    @given(filesystem_backend_watch_contexts(), st.temporary_directories(), st.data())
    def test_watch_file_removal(
        self, context: filesystem_backend_watch_context, secondary_base: str, data
    ):
        """Events emitted when files are deleted or moved outside of the library are
        the correct FileRemovedEvent objects.
        """
        library_base, folders, files, backend, generator = context

        removed_files = data.draw(
            st.sets(st.sampled_from(files), min_size=2, max_size=6)
        )
        for index, path in enumerate(removed_files):
            # Take turns simply deleting stuff and moving it out of the library. Both
            # actions should yield the same event.
            if index % 2 == 0:
                os.remove(os.path.join(library_base, path))
            else:
                os.rename(
                    os.path.join(library_base, path),
                    os.path.join(secondary_base, str(index)),
                )
            event = next(generator)
            self.assertIsInstance(event, events.FileRemovedEvent)
            self.assertEqual(event.path, path)

        self.assertIs(generator.send("check_empty"), True)

    @settings(**FILESYSTEM_BACKEND_SETTINGS)
    @given(filesystem_backend_watch_contexts(), st.temporary_directories(), st.data())
    def test_watch_folder_moving(
        self, context: filesystem_backend_watch_context, secondary_base: str, data
    ):
        """Events emitted when folders are moved in and out of the library are the
        correct NewFileEvent and FolderRemovedEvent objects.
        """
        library_base, folders, files, backend, generator = context

        new_folder = data.draw(st.directory_names(exclude=folders))
        new_files = data.draw(st.sets(st.filenames(), min_size=2, max_size=6))

        # Create a new folder outside of the base directory and move it inside of the
        # library. This should yield a NewFileEvent for each file.
        os.mkdir(os.path.join(secondary_base, new_folder))
        for filename in new_files:
            with open(os.path.join(secondary_base, new_folder, filename), "w") as f:
                f.write(data.draw(st.text()))
        os.rename(
            os.path.join(secondary_base, new_folder),
            os.path.join(library_base, new_folder),
        )
        # Prepend the new folder path to the filenames to make them paths relative to
        # the library root.
        new_files = list(map(partial(os.path.join, new_folder), new_files))
        # Check that all events are present.
        for event in [next(generator) for _ in range(len(new_files))]:
            self.assertIsInstance(event, events.NewFileEvent)
            self.assertIn(event.path, new_files)
            new_files.remove(event.path)
        self.assertEqual(len(new_files), 0)

        # Move the folder outside of the library again. This should yield a
        # FolderRemovedEvent.
        os.rename(
            os.path.join(library_base, new_folder),
            os.path.join(secondary_base, new_folder),
        )
        event = next(generator)
        self.assertIsInstance(event, events.FolderRemovedEvent)
        self.assertEqual(event.path, new_folder)

        self.assertIs(generator.send("check_empty"), True)

    @settings(**FILESYSTEM_BACKEND_SETTINGS)
    @given(filesystem_backend_watch_contexts(), st.data())
    def test_watch_folder_moving_inside(
        self, context: filesystem_backend_watch_context, data
    ):
        """Events emitted when files and folders are moved inside of the library
        are the correct NewFileEvent and FolderRemovedEvent objects.
        """
        library_base, folders, files, backend, generator = context

        source_file = data.draw(st.sampled_from(files))
        target_folder = data.draw(st.sampled_from(folders))
        new_file = data.draw(st.filenames(exclude=files))
        os.rename(
            os.path.join(library_base, source_file),
            os.path.join(library_base, target_folder, new_file),
        )
        event = next(generator)
        self.assertIsInstance(event, events.FileMovedEvent)
        self.assertEqual(event.old_path, source_file)
        self.assertEqual(event.new_path, os.path.join(target_folder, new_file))

        target_folder = data.draw(st.sampled_from(folders[1:]))
        new_folder = data.draw(st.directory_names(exclude=folders))
        os.rename(
            os.path.join(library_base, target_folder),
            os.path.join(library_base, new_folder),
        )
        event = next(generator)
        self.assertIsInstance(event, events.FolderMovedEvent)
        self.assertEqual(event.old_path, target_folder)
        self.assertEqual(event.new_path, new_folder)

        self.assertIs(generator.send("check_empty"), True)

    @settings(**FILESYSTEM_BACKEND_SETTINGS)
    @given(filesystem_backend_watch_contexts(), st.temporary_directories(), st.data())
    def test_watch_creation(
        self, context: filesystem_backend_watch_context, secondary_base: str, data
    ):
        """Events emitted when files are created in the library or moved into the
        library from outside are the correct NewFileEvent objects."""
        library_base, folders, files, _, generator = context

        new_files = data.draw(
            st.sets(st.filenames(exclude=files), min_size=2, max_size=6)
        )

        def create_file(path):
            with open(path, "w") as f:
                f.write(data.draw(st.text()))

        for index, filename in enumerate(new_files):
            # Take turns creating new stuff in the library and moving it in from
            # outside. Both actions should yield the same event.
            library_path = os.path.join(data.draw(st.sampled_from(folders)), filename)
            absolute_path = os.path.join(library_base, library_path)
            if index % 2 == 0:
                create_file(absolute_path)
            else:
                tmp_path = os.path.join(secondary_base, "tmp")
                create_file(tmp_path)
                os.rename(tmp_path, absolute_path)

            event = next(generator)
            self.assertIsInstance(event, events.NewFileEvent)
            self.assertEqual(event.path, library_path)

        self.assertIs(generator.send("check_empty"), True)
