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
created. The exact types here depend on the library's context. This context also
defines how you can retrieve this information in the API - each implementation
provides it's own methods. As mentioned before, the only context implemented at
the moment is the :ref:`timeline <guide-timeline>`.

.. _guide-library-content:

Library content objects
-----------------------

As mentioned before, most of what Tumpara can store is organized into libraries.
In general, these types of objects are referred to as *library content*, files
being one example here. Another instance of library content objects are
:ref:`timeline entries <guide-timeline>`.

Visibility
~~~~~~~~~~

Library content objects have a *visibility* property. This is an enum that
denotes who is able to access it. There are five possible values for this
property:

- **Public** entries are visible to everyone, even users that are not logged
  in.
- **Internal** entries can be seen by anyone who is logged in on the server.
- Entries marked with **member-only** can only be seen by users which are a
  member of the entry's library.
- For **owner-only** entries to be seen, the user must be an owner of the
  corresponding library (have write access).
- The last possibility is to unset this field on the entry itself. Then, the
  visibility is inferred by the library's *default visibility* setting, which
  can have the same four aforementioned values.
