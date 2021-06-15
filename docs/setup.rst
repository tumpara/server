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

Docker
~~~~~~

The main supported way to run Tumpara is through Docker. The documentation here
will follow.

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
