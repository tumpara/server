.. _settings:

Settings reference
==================

Tumpara is configured using a Python file which is loaded on startup. The
environment variable ``DJANGO_SETTINGS_MODULE`` determines the name of this
file. All of the `Django settings`_ will work as expected – a few of the most
relevant ones are also listed below for completeness' sake. See the
aforementioned documentation for a more complete list. On top of the
Django-provided settings, there are a few which are unique to Tumpara. This
page aims to provide a complete reference of all the knobs you can tweak to
configure your installation.

.. _Django settings: https://docs.djangoproject.com/en/3.2/ref/settings/

Core settings
-------------

This section contains core settings required for the application to run. With
the exception of ``SECRET_KEY``, these are all defined by the default
configuration.

``SECRET_KEY``
~~~~~~~~~~~~~~

This is the only setting you *need* to define. This key is used everywhere where
encryption or cryptographic signing is required, for example with user sessions.

It should be a string. Use a command like ``openssl rand -base64 32`` to
generate a secure key for you.

.. warning::
  Make sure this value is kept secret!

  As a minimum, run ``chmod go-rwx local_settings.py`` on your configuration
  file. Further, the web server should always be running as it's own user for
  production instances.

----

``DATABASES``
~~~~~~~~~~~~~

Use this to configure the database that Tumpara will use. See
`Django's documentation`_ on this key for the exact syntax. Just make sure it's
a database type that is `supported`_ by GeoDjango.

.. _Django's documentation: https://docs.djangoproject.com/en/3.2/ref/settings/#databases
.. _supported: https://docs.djangoproject.com/en/3.2/ref/contrib/gis/db-api/#spatial-backends

Default: an SQLite database named ``db.sqlite3`` in the project's root folder.

----

.. _settings-allowed-hosts:

``ALLOWED_HOSTS``
~~~~~~~~~~~~~~~~~

Set this to the list of all hosts that are allowed to serve your instance of
Tumpara. If you would like it to be reachable from both the server's IP address
as well as a domain name, add them here. For example, your configuration could
look like this:

.. code-block:: python

  ALLOWED_HOSTS = ["127.0.0.1", "192.168.1.50", "tumpara.example.org"]

This will help mitigating Host-header attacks. See documentation on
`djangoproject.com`_ for more details on what this option does.

.. _djangoproject.com: https://docs.djangoproject.com/en/3.2/ref/settings/#allowed-hosts

Default: no hosts are allowed.

----

``PREVIEW_ROOT``
~~~~~~~~~~~~~~~~

The directory to use for caching image previews. Thumbnails will be stored in
this directory.

Default: the subdirectory ``data/previews`` under the project's root folder.

----

Application settings
--------------------

Settings in this section control how the app behaves and what defaults are
applied in certain contexts.


``BLURHASH_SIZE``
~~~~~~~~~~~~~~~~~

Tumpara supports generating `blurhashes`_ from photos, which are small textual
representations of images. These can be used by to render a blurred version of
the image while the full-scale version is still loading. This setting sets the
approximate number of components hashes should have. Lower values will result
in results which are smaller but also have less details.

.. _blurhashes: https://blurha.sh/

Default: ``12``

----

``REPORT_INTERVAL``
~~~~~~~~~~~~~~~~~~~

When performing long-running tasks like scanning, this is the interval between
items where progress is reported. If you have smaller (or larger) than average
libraries, you might want to tweak this value.

Default: ``500``
