.. _settings:

Settings reference
==================

Tumpara is configured using a Python file which is loaded on startup. All of
the `Django settings`_ will work as expected – a few of the most
relevant ones are also listed below for completeness' sake. See the
documentation linked above for a more complete list. On top of the
Django-provided settings, there are a few which are unique to Tumpara. This
page aims to provide a complete reference of all the knobs you can tweak to
configure your installation.

.. _Django settings: https://docs.djangoproject.com/en/3.2/ref/settings/

Some of the more common settings (and all of the Tumpara-specific ones) are also
available to be configured using environment variables. That way you don't need
to create a configuration file and only tweak a few options. This also makes
Docker-based deployments easier. But if you do want to create your own
configuration file, this is a good start:

.. code-block:: python

  import os

  os.environ.setdefault("TUMPARA_SECRET_KEY", "changeme")

  from tumpara.settings.production import *

  ALLOWED_HOSTS = ["localhost", "tumpara.example.com"]

In order for your custom configuration to be loaded, you need to set the
``DJANGO_SETTINGS_MODULE`` environment variable, while also making sure that
the file is found. The easiest way to do that is to name the settings file
``local_settings.py`` and put it in the working directory where you start the
server. Then, set the aforementioned variable to ``local_settings``:

.. code-block:: shell

  $ DJANGO_SETTINGS_MODULE=local_settings ./manage.py
  or
  $ DJANGO_SETTINGS_MODULE=local_settings gunicorn tumpara.wsgi

.. note::
  For regular deployments, you shouldn't need to create your own custom Django
  settings file. Check if you can use environment variables first, then create
  a settings file if that doesn't cover your needs.

Core settings
-------------

This section contains core settings required for the application to run. With
the exception of ``SECRET_KEY``, these are all defined by the default
configuration.

Secret key
~~~~~~~~~~

| *Environment variable: TUMPARA_SECRET_KEY*
| *Django setting: SECRET_KEY*

This is the only setting you *need* to define. This key is used everywhere where
encryption or cryptographic signing is required, for example with user sessions.

It should be a string. Use a command like ``openssl rand -base64 32`` to
generate a secure key for you.

.. warning::
  Make sure this value is kept secret!

  As a minimum, run ``chmod go-rwx local_settings.py`` on your configuration
  file. Further, the web server should always be running as it's own user for
  production instances.

Database setup
~~~~~~~~~~~~~~

| *Django setting: DATABASES*

Use this to configure the database that Tumpara will use. See
`Django's documentation`_ on this key for the exact syntax. Just make sure it's
a database type that is `supported`_ by GeoDjango.

.. _Django's documentation: https://docs.djangoproject.com/en/3.2/ref/settings/#databases
.. _supported: https://docs.djangoproject.com/en/3.2/ref/contrib/gis/db-api/#spatial-backends

Default: an SQLite database named ``db.sqlite3`` in the project's root folder.


.. _settings-allowed-hosts:

Application hostname
~~~~~~~~~~~~~~~~~~~~

| *Environment variable: TUMPARA_HOST (only supports a single hostname)*
| *Django setting: ALLOWED_HOSTS*

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

Data directory
~~~~~~~~~~~~~~

| *Environment variable: TUMPARA_DATA_ROOT*
| *Django setting: DATA_ROOT*

The directory to use for storing application data. If you use the default
SQLite-based database, it will be placed in this folder. Other things like the
preview (thumbnail) cache also go here.

Default: the subdirectory ``data/`` under the project's root folder, or
``/data`` when running in Docker.

Logging
~~~~~~~

| *Environment variable: LOG_LEVEL*
| *Django setting: LOGGING*

See `Django's reference`_ on this entry's format. The default setup should suit
most needs here, but you can use the environment variable above to globally
adjust how verbose the app is. It should be set to one of the following values:

.. _Django's reference: https://docs.djangoproject.com/en/3.2/ref/settings/#logging

- ``DEBUG``
- ``INFO``
- ``WARNING``

Application settings
--------------------

Settings in this section control how the app behaves and what defaults are
applied in certain contexts.

Blurhash sizes
~~~~~~~~~~~~~~

| *Environment variable: TUMPARA_BLURHASH_SIZE*
| *Django setting: BLURHASH_SIZE*

Tumpara supports generating `blurhashes`_ from photos, which are small textual
representations of images. These can be used by to render a blurred version of
the image while the full-scale version is still loading. This setting sets the
approximate number of components hashes should have. Lower values will result
in results which are smaller but also have less details.

.. _blurhashes: https://blurha.sh/

Default: ``12``

Reporting interval
~~~~~~~~~~~~~~~~~~

| *Environment variable: TUMPARA_REPORT_INTERVAL*
| *Django setting: REPORT_INTERVAL*

When performing long-running tasks like scanning, this is the interval between
items where progress is reported. If you have smaller (or larger) than average
libraries, you might want to tweak this value.

Default: ``500``

Docker-specific settings
------------------------

Settings in this section are only relevant to Docker-based deployments and are
interpreted by the container's entrypoint script.

Additional user groups
~~~~~~~~~~~~~~~~~~~~~~

| *Environment variable: TUMPARA_EXTRA_GROUPS*

If your media libraries aren't publicly readable because of filesystem
permissions, you can set this variable to a space-separated list of group IDs
that the container's user will be added to. Find out your user's groups with
``id`` and add the necessary ones to this list. The account that runs Tumpara in
the container will receive the additional groups on startup. For example, if
your receive this output...

.. code-block:: shell

  $ id
  uid=1000(myuser) gid=1000(myuser) Groups=1000(myuser),985(users)

... you would set ``TUMPARA_EXTRA_GROUPS=985`` if the corresponding media
directories are owned by the ``users`` group.
