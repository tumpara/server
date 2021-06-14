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

.. code-block:: shell

    pip install ".[prod]"

This will install Tumpara, it's dependencies and gunicorn so that you can run
the app production-ready. Next, generate a secret key - for example using
``openssl rand -base64 32``. The final step before running the server is to
create a configuration file. Create a file named ``local_settings.py`` with the
following config:

..
  TODO: We should add a test to make sure the server will run with this config.

.. code-block:: python

  from tumpara.settings.prod import *

  SECRET_KEY = "YOUR_SECRET_KEY"

  # Change this to your instance's domain or IP address (without the port).
  ALLOWED_HOSTS = ["localhost"]

These are only the minimal settings required to run. For a complete list, see
:ref:`this page <settings>`. As a starting point, you might want to change the
default database and the ``PREVIEW_ROOT`` setting. Then the app can
be run with the following command:

.. code-block:: shell

  DJANGO_SETTINGS_MODULE=local_settings gunicorn --bind 0.0.0.0:8000 tumpara.wsgi

.. _libraries: https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/geolibs/
