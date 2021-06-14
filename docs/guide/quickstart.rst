.. _guide-quickstart:

Quick start
===========

.. note::
  This guide assumes you have `installed <installation>`_ Tumpara already. If
  you haven't, see the other page first and then head back here!

Once you have your server set up, the first step is to create an admin user:

.. code-block:: shell

  $ ./manage.py createsuperuser

After that, login in to Django's admin backend by visiting ``/admin`` under the
link your app is published at. Here, you will want to create a
:ref:`library <guide-libraries>`. Since nothing else is implemented yet, use
``timeline`` for the context setting and ``file:///path/to/your/collection`` as
the source. If you are using the Docker container, make sure to mount the folder
from outside into the container, for example under ``/media/photos``. In that
case you would use ``file:///media/photos`` as the source.

Then add yourself as an owner to the library. Once that is done, scan for files:

.. code-block:: shell

  $ ./manage.py scan
  Or in the Docker image:
  $ docker-compose exec server ./manage.py scan

Now you should be set up to open the web client and see your media collection.
