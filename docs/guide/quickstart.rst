.. _guide-quickstart:

Quick start
===========

This guide assumes you have `installed <installation>`_ Tumpara already. If
you haven't, see the other page first and then head back here! Once you have
your server set up, the first step is to create an admin user:

.. code-block:: shell

  $ ./manage.py createsuperuser

.. note::
  How exactly you need to execute ``./manage.py`` depends on your installation
  method. To keep this guide as generic as possible, examples on this page
  invoke the script directly.

  If you used Docker to setup the server, you would run the example above like
  this:

  .. code-block:: shell

    $ docker-compose exec server ./manage.py createsuperuser

  In case you did not use the Docker-Compose stack as described in the
  :ref:`setup tutorial <installation-docker>`, run it without Compose (replace
  ``tumpara-server`` with the name of your container):

  .. code-block:: shell

    $ docker exec -it tumpara-server ./manage.py createsuperuser


After that, login in to Django's admin backend by visiting ``/admin`` under the
link your instance is published at. Here, you will want to create a
:ref:`library <guide-libraries>`. Using a library, you can tell Tumpara which
folders on your system to scan for content. Create a new library using these
settings:

- Context: ``timeline``. This is the only value currently supported here.
- Source: the path to your desired folder: ``file:///path/to/your/folder``. If
  your are using docker, make sure to `bind mount`_ the folder from the host into
  the container, then use the path in the container here. For example, if you
  have defined a volume as ``/home/user/Photos:/media/photos:ro``, use
  ``file:///media/photos`` as the library's source field.

.. _bind mount: https://docs.docker.com/storage/bind-mounts/

.. note::
  Tumpara contains a demo backend that takes images from the `Unsplash dataset`_
  and uses them to fill the library. If you don't have a holder full of pictures
  at hand or only want to quickly test out the project, use
  ``demo://?limit=2000`` as the source value. You may specify a limit to the
  maximum number of images that are downloaded.

  .. _Unsplash dataset: https://unsplash.com/data

Then add yourself as an owner to the library. If you like, you can add more
users and / or libraries, adding them as members or owners as well. Once you are
happy with your setup, you can scan the filesystem for content:

.. code-block:: shell

  $ ./manage.py scan

Depending on the size of your dataset (and also the type of database you are
using), this make take a while. Sit back and relax while Tumpara populates your
database with content. Once this is done, you should already see some *File*
objects in the admin backend. If so, great! Now you can open the web client and
start browsing.
