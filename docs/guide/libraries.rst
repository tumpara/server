.. _guide-libraries:

Libraries
=========

Everything in Tumpara is organized into *libraries*. In order for your files to
be found, you will need to create one in the admin interface. When you do so,
there are two settings work pointing out:

- The **source** defines *where* files come from. This is an URI that tells the
  library which backend to use. Currently, the only support backend is the file
  system. For example, if you would like to use items in the directory
  ``/mnt/media/Photos``, set this to ``file:///mnt/media/Photos`` (note the
  three slashes).
- By giving a library a **context** you tell it *which part* of Tumpara should
  handle files. This determines which types of files are supported in this
  library. Currently, only one context has been implemented so just set this
  to ``timeline``.

After you have created the library, add yourself as an owner. Then save it and
hit the 'Scan' button. This make take a while, depending on the size of your
collection. Alternatively, you can run this management command:

.. code-block:: shell

  $ ./manage.py scan

See the :ref:`storage reference <storage>` for a more in-depth overview on
libraries.

.. _guide-files:

Files
-----

After scanning a library, file objects of the corresponding types will have been
created. Use a client to see them.
