.. _storage:

Storage system
==============

`Libraries <guide-libraries>`_ created in the API are modeled almost exactly the
same way in the backend:

.. autoclass:: tumpara.storage.models.Library
  :members:
  :exclude-members: DoesNotExist, MultipleObjectsReturned

Scanning
--------

To scan a library for changes, call it's
:meth:`scan() <tumpara.storage.models.Library.scan>` method. Alternatively,
there is also a management command:

.. code-block:: shell

  ./manage.py scan

Files and handlers
------------------

The model for `files <guide-files>`_ is also very similar to the API type:

.. autoclass:: tumpara.storage.models.File
  :members:
  :exclude-members: DoesNotExist, MultipleObjectsReturned

In contrast to the API though, you can see that the backend type has a
`generic relation`_ to something called a *Handler*. This handler exposes
functionality specific to the file type. Depending on the ``context`` field in
the corresponding library, different handlers are available. When a new file is
scanned, the
:meth:`analyze_file() <tumpara.storage.models.FileHandler.analyze_file>` method
is called on every applicable handler type (those with the same context as the
library). Once the file is accepted by some handler, it will be instantiated by
that type.

.. _generic relation: https://docs.djangoproject.com/en/3.2/ref/contrib/contenttypes/

As an example, the :class:`Photo <tumpara.content.gallery.models.Photo>` handler is
exposed in the ``timeline`` context. When you create a library with that
context and scan it, that handler's ``analyze_file`` method will be called. It
will raise exceptions for everything that is not an image. If a newly found file
is an image, though it will be accepted (the analyze method doesn't return
anything in this case). Then, the :class:`File <tumpara.storage.models.File>` object
will be initialized with a handler of this type.

Registering new file types
~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to support a new type of file, you will need to implement the following
abstract model:

.. autoclass:: tumpara.storage.models.FileHandler
  :members:
  :exclude-members: DoesNotExist, MultipleObjectsReturned

To make extending the storage framework easy, a decorator is provided to
register the new file type for a given library context. The handler will then be
a candidate for any library with the given string set as it's context.

.. automethod:: tumpara.storage.register_file_handler

For a more complete example, have a look at the following code:

.. code-block:: python

  from tumpara.storage import register_file_handler
  from tumpara.storage.models import FileHandler, InvalidFileTypeError

  class FooEndingHandler(FileHandler):
      """File handler that takes files that end in '.foo'."""

      @classmethod
      def analyze_file(cls, library: Library, path: str):
          if not path.endswith(".foo"):
              raise InvalidFileTypeError

      def scan_from_file(self, **kwargs):
          with self.open():
              # Do something with the file now, for example scanning metadata.
              pass

Storage backends
----------------

Each library has a ``source`` field with determines where to search for files
when scanning. This should be an URI like ``foo://user:password@server/path``,
although depending on the type not all components are mandatory. The scheme (in
this example ``foo`` determines which Backend to use. Backends are
`Django storage objects`_ with a few extra methods to aid scanning.

Currently, Tumpara only comes with one backend - the file system. You can use
it by specifying a source value like this: ``file:///path/to/folder``. Note the
triple-slash. If you would like to extend the project and add another type of
backend, see the following section.

.. _Django storage objects: https://docs.djangoproject.com/en/3.2/howto/custom-file-storage/

Adding a new backend
~~~~~~~~~~~~~~~~~~~~

Similarly to registering file handlers, in order to add a custom storage
backend, you need to extend the following base class:

.. autoclass:: tumpara.storage.backends.LibraryBackend
  :members:
  :special-members: __init__


You will need to at least implement the constructor,
:meth:`check() <tumpara.storage.backends.LibraryBackend.check>` as well as
|exists|_, |get_modified_time|_ and |open|_ from the Django API in order for
scanning to work correctly. Then, register it using this decorator:

.. |exists| replace:: ``exists``
.. _exists: https://docs.djangoproject.com/en/3.2/ref/files/storage/#django.core.files.storage.Storage.exists
.. |get_modified_time| replace:: ``get_modified_time``
.. _get_modified_time: https://docs.djangoproject.com/en/3.2/ref/files/storage/#django.core.files.storage.Storage.get_modified_time
.. |open| replace:: ``open``
.. _open: https://docs.djangoproject.com/en/3.2/ref/files/storage/#django.core.files.storage.Storage.open

.. automethod:: tumpara.storage.register_library_backend

Here is a full example:

.. code-block:: python

  from django.core.exceptions import ValidationError

  from tumpara.storage import register_file_handler
  from tumpara.storage.models import FileHandler, InvalidFileTypeError

  @register_library_backend("dummy")
  class DummyBackend(FileHandler):
      """File handler that takes files that end in '.foo'."""

      def __init__(self, parsed_uri: ParseResult):
          self.username = parsed_uri.username

      def check(self):
          if self.username is None or len(self.username) > 0:
              raise ValidationError(
                  "A username must be provided when using DummyBackend."
              )

      # And more methods...
      # You will need to implement exists, get_modified_time, open for a minimum
      # working example.

This will handle libraries with a scheme of ``dummy``. In practice it may be
easier to base a new backend off of an existing Django storage backend. The
built-in ``file`` backend works exactly like this. See this snippet:

.. literalinclude:: ../../tumpara/storage/backends/file.py
  :language: python
  :lines: 21-34
  :lineno-start: 21
  :linenos:
  :emphasize-lines: 2,4
