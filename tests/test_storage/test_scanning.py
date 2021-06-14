import io
import os
import os.path
import shutil
from tempfile import mkdtemp
from urllib.parse import ParseResult

import inotify_simple
from django.utils import timezone
from hypothesis import assume
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from tumpara.storage import register_library_backend
from tumpara.storage.backends import LibraryBackend
from tumpara.storage.models import Library
from tumpara.storage.scanner import events
from tumpara.testing import state_machine_to_test_function
from tumpara.testing import strategies as st

from .models import GenericFileHandler


@register_library_backend("test")
class TestingBackend(LibraryBackend):
    """Library backend that looks up file contents from a dictionary."""

    data = None

    def __init__(self, parsed_uri: ParseResult):
        pass

    def check(self):
        return True

    def open(self, name, mode="rb"):
        assert (
            mode == "rb"
        ), "The testing backend only supports opening files with mode 'rb'."
        if name not in self.data:
            raise FileNotFoundError(f"File path {name!r} not found in dataset.")
        return io.BytesIO(self.data[name])

    def get_modified_time(self, name):
        return timezone.now()

    def exists(self, name):
        return name in self.data


class LibraryActionsStateMachine(RuleBasedStateMachine):
    """Test case that repeatedly performs random file actions on a library and
    ensures the state is resembled in the database as expected.

    This is the base class for individual test cases.
    """

    def __init__(self):
        super().__init__()

        # This set holds all folders that have been created (including the root folder).
        self.folders = {""}
        # Dictionary of the contents of all files that have been written. It will be
        # tested that the GenericFileHandler mapped it correctly.
        self.files = {}
        # Timestamps of when files have changed.
        self.file_timestamps = {}
        # Keep a list of events for debugging purposes.
        self.events = []

        self._init_library()

    @rule(filename=st.filenames(), content=st.binary(min_size=1), data=st.data())
    def add_file(self, filename: str, content: bytes, data: st.DataObject):
        """Create a new file and write some content."""
        folder = data.draw(st.sampled_from(list(self.folders)))
        path = os.path.join(folder, filename)
        assume(path not in self.files)

        self.files[path] = content
        self.file_timestamps[path] = timezone.now()
        self.events.append(f"_add_file {path!r} {content!r}")
        self._add_file(path, content, data=data)

    @rule(name=st.directory_names(), data=st.data())
    def add_folder(self, name, data: st.DataObject):
        """Create an empty folder."""
        parent = data.draw(st.sampled_from(list(self.folders)))
        path = os.path.join(parent, name)
        assume(path not in self.folders)

        self.folders.add(path)
        self.events.append(f"_add_folder {path!r}")
        self._add_folder(path, data=data)

    @precondition(lambda self: len(self.files) >= 1)
    @rule(data=st.data())
    def delete_file(self, data: st.DataObject):
        """Delete a file."""
        path = data.draw(st.sampled_from(list(self.files.keys())))
        del self.files[path]
        del self.file_timestamps[path]
        self.events.append(f"_delete_file {path!r}")
        self._delete_file(path, data=data)

    @precondition(lambda self: len(self.folders) >= 2)
    @rule(data=st.data())
    def delete_folder(self, data: st.DataObject):
        """Delete a folder (and everything in it)."""
        path = data.draw(st.sampled_from([f for f in self.folders if f != ""]))
        path_with_slash = os.path.join(path, "")

        self.folders = {
            f for f in self.folders if f != path and not f.startswith(path_with_slash)
        }
        for file_path in list(self.files.keys()):
            if file_path.startswith(path_with_slash):
                del self.files[file_path]
                del self.file_timestamps[file_path]

        self.events.append(f"_delete_folder {path!r}")
        self._delete_folder(path, data=data)

    @precondition(lambda self: len(self.folders) >= 2 and len(self.files) >= 1)
    @rule(name=st.filenames(), data=st.data())
    def move_file(self, name: str, data: st.DataObject):
        """Move a file into another folder."""
        old_path = data.draw(st.sampled_from(list(self.files.keys())))
        old_folder = os.path.dirname(old_path)
        new_folder = data.draw(
            st.sampled_from([f for f in self.folders if f != old_folder])
        )
        new_path = os.path.join(new_folder, name)
        assume(new_path not in self.files)

        self.files[new_path] = self.files[old_path]
        self.file_timestamps[new_path] = self.file_timestamps[old_path]
        del self.files[old_path]
        del self.file_timestamps[old_path]

        self.events.append(f"_move_file {old_path!r} {new_path!r}")
        self._move_file(old_path, new_path, data=data)

    @precondition(lambda self: len(self.files) >= 1)
    @rule(content=st.binary(min_size=1), data=st.data())
    def change_file(self, content: bytes, data: st.DataObject):
        """Change the contents of a file."""
        path = data.draw(st.sampled_from(list(self.files.keys())))
        assume(content != self.files[path])
        self.files[path] = content
        self.file_timestamps[path] = timezone.now()
        self.events.append(f"_change_file {path!r} {content!r}")
        self._change_file(path, content, data=data)

    @precondition(lambda self: len(self.folders) >= 3)
    @rule(name=st.directory_names(), data=st.data())
    def move_folder(self, name: str, data: st.DataObject):
        old_path = data.draw(st.sampled_from([f for f in self.folders if f != ""]))
        parent = data.draw(
            st.sampled_from(
                [
                    f
                    for f in self.folders
                    if f not in [old_path]
                    and not f.startswith(os.path.join(old_path, ""))
                ]
            )
        )
        new_path = os.path.join(parent, name)
        assume(new_path not in self.folders)

        self.folders.remove(old_path)
        self.folders.add(new_path)
        old_path_slash = os.path.join(old_path, "")
        for folder_path in list(self.folders):
            if folder_path.startswith(old_path_slash):
                relative_folder_path = os.path.relpath(folder_path, old_path)
                self.folders.add(os.path.join(new_path, relative_folder_path))
                self.folders.remove(folder_path)

        for file_path in list(self.files.keys()):
            if file_path.startswith(old_path_slash):
                relative_file_path = os.path.relpath(file_path, old_path)
                new_file_path = os.path.join(new_path, relative_file_path)
                self.files[new_file_path] = self.files[file_path]
                self.file_timestamps[new_file_path] = self.file_timestamps[file_path]
                del self.files[file_path]
                del self.file_timestamps[file_path]

        self.events.append(f"_move_folder {old_path!r} {new_path!r}")
        self._move_folder(old_path, new_path, data=data)

    @precondition(lambda self: len(self.files) >= 2)
    @rule(data=st.data())
    def swap_files(self, data: st.DataObject):
        """Draw a list of file paths and move them around in a circle."""
        paths = data.draw(
            st.lists(
                st.sampled_from(list(self.files.keys())),
                min_size=2,
                max_size=len(self.files),
                unique=True,
            )
        )
        temp_path = data.draw(st.filenames(exclude=list(self.files.keys())))

        self.files[temp_path] = self.files[paths[0]]
        self.file_timestamps[temp_path] = self.file_timestamps[paths[0]]
        self._move_file(paths[0], temp_path, data=data)

        for i in range(1, len(paths)):
            self.files[paths[i - 1]] = self.files[paths[i]]
            self.file_timestamps[paths[i - 1]] = self.file_timestamps[paths[i]]
            self._move_file(paths[i], paths[i - 1], data=data)

        self.files[paths[-1]] = self.files[temp_path]
        self.file_timestamps[paths[-1]] = self.file_timestamps[temp_path]
        del self.files[temp_path]
        del self.file_timestamps[temp_path]
        self._move_file(temp_path, paths[-1], data=data)

    def assert_library_state(self, library: Library):
        """Helper method that asserts the state of a given library matches what is on
        record."""
        assert set(self.files.keys()) == set(self.file_timestamps.keys())
        for path, content in self.files.items():
            file = library.files.get(path=path, orphaned=False)
            assert isinstance(file.handler, GenericFileHandler)
            assert file.handler.initialized
            assert file.handler.content == content
            assert file.handler.file == file
            assert file.last_scanned >= self.file_timestamps[path]
        assert library.files.filter(orphaned=False).count() == len(self.files)

    def _init_library(self):
        raise NotImplementedError

    def _add_file(self, path: str, content: bytes, data: st.DataObject):
        raise NotImplementedError

    def _add_folder(self, path: str, data: st.DataObject):
        raise NotImplementedError

    def _delete_file(self, path: str, data: st.DataObject):
        raise NotImplementedError

    def _delete_folder(self, path: str, data: st.DataObject):
        raise NotImplementedError

    def _move_file(self, old_path: str, new_path: str, data: st.DataObject):
        raise NotImplementedError

    def _move_folder(self, old_path: str, new_path: str, data: st.DataObject):
        raise NotImplementedError

    def _change_file(self, path: str, content: bytes, data: st.DataObject):
        raise NotImplementedError


class EventHandling(LibraryActionsStateMachine):
    """Individual test cases for each file event."""

    def _init_library(self):
        if TestingBackend.data is not None:
            raise RuntimeError("the EventHandling test cannot be run in parallel")
        TestingBackend.data = self.files
        self.library = Library.objects.create(context="testing", source=f"test://none")

    def teardown(self):
        TestingBackend.data = None

    def _add_file(self, path: str, content: bytes, data: st.DataObject):
        # Randomly commit either a NewFileEvent or a FileModified event, as these
        # should both handle new files (in case of the latter because the file does
        # not exist in the database yet).
        if data.draw(st.booleans()):
            events.NewFileEvent(path).commit(self.library)
        else:
            events.FileModifiedEvent(path).commit(self.library)

    def _add_folder(self, path: str, **kwargs):
        # There is no new folder event.
        pass

    def _delete_file(self, path: str, **kwargs):
        events.FileRemovedEvent(path).commit(self.library)

    def _delete_folder(self, path: str, **kwargs):
        events.FolderRemovedEvent(path).commit(self.library)

    def _move_file(self, old_path: str, new_path: str, **kwargs):
        events.FileMovedEvent(old_path, new_path).commit(self.library)

    def _move_folder(self, old_path: str, new_path: str, **kwargs):
        events.FolderMovedEvent(old_path, new_path).commit(self.library)

    def _change_file(self, path: str, content: bytes, **kwargs):
        events.FileModifiedEvent(path).commit(self.library)

    @rule(data=st.data())
    def remove_untracked_file(self, data: st.DataObject):
        """Fire a file remove event for a file that is not tracked by the library."""
        path = data.draw(st.filenames(exclude=list(self.files.keys())))
        events.FileRemovedEvent(path).commit(self.library)

    @invariant()
    def check_state(self):
        self.assert_library_state(self.library)


class FilesystemScanning(LibraryActionsStateMachine):
    """Complete test case for the scanning scenario with the filesystem backend."""

    def _init_library(self):
        # Initialize the main library that will be used for testing.
        self.root = mkdtemp()
        self.library = Library.objects.create(
            context="testing", source=f"file://{self.root}"
        )

        # Create a second library with the same source. This will be scanned with the
        # slow=True option.
        self.slow_library = Library.objects.create(
            context="testing",
            # Adding a slash to fool the unique constraint ^-^
            source=f"file://{self.root}/",
        )

        # Create a third library with the same source. This will be scanned by
        # watching the backend because that yields slightly different events for some
        # actions and we want to test those as well.
        self.watched_library = Library.objects.create(
            context="testing",
            # Again, we need the slash to fool the unique constraint.
            source=f"file://{self.root}//",
        )
        self.watch_events = self.watched_library.backend.watch()
        assert next(self.watch_events) is None

    def teardown(self):
        shutil.rmtree(self.root)

    def _add_file(self, path: str, content: bytes, **kwargs):
        full_path = os.path.join(self.root, path)
        with open(full_path, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.utime(full_path)

    def _add_folder(self, path: str, **kwargs):
        os.mkdir(os.path.join(self.root, path))

    def _delete_file(self, path: str, **kwargs):
        os.unlink(os.path.join(self.root, path))

    def _delete_folder(self, path: str, **kwargs):
        shutil.rmtree(os.path.join(self.root, path))

    def _move_file(self, old_path: str, new_path: str, **kwargs):
        os.rename(os.path.join(self.root, old_path), os.path.join(self.root, new_path))

    def _move_folder(self, old_path: str, new_path: str, **kwargs):
        self._move_file(old_path, new_path)

    def _change_file(self, path: str, content: bytes, **kwargs):
        # When modifying files, we sometimes need to actually make sure the OS has fired
        # the corresponding events before continuing. That way we try to eliminate race
        # conditions while testing. Also, we check the file timestamps - just to be
        # sure.
        inotify = inotify_simple.INotify()
        inotify.add_watch(
            os.path.dirname(os.path.join(self.root, path)), inotify_simple.flags.MODIFY
        )
        inotify.read(timeout=0)

        before_time = self.watched_library.backend.get_modified_time(path)
        self._add_file(path, content)
        after_time = self.watched_library.backend.get_modified_time(path)
        assert before_time < after_time

        inotify.read()

    @invariant()
    def perform_scan(self):
        """Run the scan on both libraries and make sure the state is OK."""
        self.library.scan(watch=False, thread_count=1, slow=False)
        self.assert_library_state(self.library)

        self.slow_library.scan(watch=False, thread_count=1, slow=True)
        self.assert_library_state(self.slow_library)

        while True:
            event = self.watch_events.send(0)
            if event is None:
                break
            event.commit(self.watched_library)
        self.assert_library_state(self.watched_library)


test_event_handling = state_machine_to_test_function(
    EventHandling, use_django_executor=True
)
test_filesystem_scanning = state_machine_to_test_function(
    FilesystemScanning, use_django_executor=True
)
