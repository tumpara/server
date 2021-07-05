Setup and basic usage
=====================

While this guide is still a bit rudimentary, it should help you get the server
up and running so that you can start trying it out. Please don't hesitate to
reach out if you find that something is missing!

Once you have completed this setup tutorial, take a look at the
:ref:`quick start guide <guide-quickstart>` for the next steps.

.. _installation:

Installation
------------

To run, Tumpara requires a GeoDjango-Supported `spacial database`_. For
moderately-sized datasets with only a few concurrent users, SQLite (with the
SpaciaLite extension) should hold up fine. Otherwise have a look at
PostgreSQL (with PostGIS). Those two are the primary databases that have been
tested with the application, so it is recommended that you stick to those.

.. _spacial database: https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/#spatial-database

.. _installation-docker:

Docker
~~~~~~

The main supported way to run Tumpara is through Docker. Here is a `Compose`_
stack that should get you up and running:

.. _Compose: https://docs.docker.com/compose/

.. literalinclude:: docker-compose/docker-compose.yml
  :language: yaml

Copy the file into an empty directory named ``tumpara``. Next to the compose
configuration, you will need a file containing environment variables to
configure your instance. Name this file ``.tumpara.env``:

.. literalinclude:: docker-compose/.tumpara.env
  :language: shell

.. warning::
  Since the environment file contains the secret key, make sure it can't be read
  by every user on the server! Set the correct permissions by running
  ``chmod 600 .tumpara.env``. Ideally, the file should be owned by root (run
  ``chown root:root .tumpara.env``), but that also means that you need to prefix
  all Docker commands with ``sudo``.

You will need to edit a few options inside these two files, most notably:

- Add a Docker volume to the server container for each media folder you would
  like to index. See the example definitions in the compose file for the basic
  idea on how to do this.
- A cryptographically secure secret key is required to run Tumpara. This is used
  to encrypt things like passwords and session keys, so you should use an
  appropriate method for generating it. If you have it installed on your system,
  use OpenSSL to create such a secret: ``openssl rand -base64 32``. Otherwise
  use some other secure random string generator (like your password manager).
  Add the key to the environment file.
- Update the web container's port definition in the compose file if you don't
  plan on using a reverse proxy like Caddy, Traefik, Nginx or similar.

You may configure additional settings according to the
:ref:`settings reference <settings>` and tweak the setup to your liking. Once
you are happy, run the following:

.. code-block:: shell

  $ docker-compose up -d

This will spin up both the server container as well as the web client, which is
an Nginx instance that will proxy API requests to the server. To run management
commands inside the container you can use Docker's ``exec`` command. This will
run the corresponding tasks directly on your instance, for example:

.. code-block:: shell

  $ docker-compose exec server ./manage.py scan

Now have a look at the :ref:`quick start guide <guide-quickstart>` for the next
steps - like adding a first user and setting up libraries.

.. note::
  You should run Tumpara behind a reverse proxy like `Caddy`_ which enables
  HTTPS, especially if your instance is publicly available. By default, the
  above compose configuration will publish Tumpara at port ``8080``.

  .. _Caddy: https://caddyserver.com/

For completeness' sake, the server exposes two Docker volumes:

- **/data** – This volume mostly contains caches for user content like image
  previews. If you are using SQLite, the database is also saved here. In the
  future, this may be split into different volumes so that replication is
  easier. In the meantime, you should include this volume in your backups.
- **/data/static** – Initially, this volume is empty. It is populated on startup
  with any static files that the backend does not serve itself – for example the
  CSS for login and admin sites. You don't need to change anything here and
  don't need to include it in your backups, as it is regenerated every time you
  restart your stack.

Standalone
~~~~~~~~~~

If you would like to run Tumpara without Docker, make sure you have installed
the `libraries`_ required by GeoDjango. Then, after cloning the repository, run
the following in the project directory:

.. _libraries: https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/geolibs/

.. code-block:: shell

    pip install ".[prod]"

This will install Tumpara, it's dependencies and gunicorn so that you can run
the app production-ready. Next, generate a secret key - for example using
``openssl rand -base64 32``. If you would like to create a custom
:ref:`settings file <settings>`, do that now (as described in the linked
reference page) and save it to the project directory as ``local_settings.py``.
If you only want to run Tumpara with minimal configuration, this won't be
necessary, though.

Before running the server, you will need to create the database. Do this with
the ``migrate`` management command:

.. code-block:: shell

  $ TUMPARA_SECRET_KEY=changeme ./manage.py migrate

.. note::
  If you have a custom configuration file, you will need to use the
  corresponding environment variable to load it. In that case, prepend
  ``DJANGO_SETTINGS_MODULE=local_settings`` to all commands mentioned in this
  guide (and subsequent management commands).

..
  TODO: We should add a test to make sure the server will run with this config.

Once the database migrations have run through, start the actual server:

.. code-block:: shell

  DJANGO_SETTINGS_MODULE=local_settings gunicorn --bind 0.0.0.0:8000 tumpara.wsgi

Now your instance should be up and running, ready to handle requests. See the
:ref:`quick start guide <guide-quickstart>` for the next steps.
