.. _guide-timeline:

Timeline
========

The *timeline* is the essential component for managing photo libraries with
Tumpara, although the system is intentionally designed to allow for additional
content types (files or otherwise). Every item in the timeline is called an
*entry*. Entries have one main attribute (next to their ID) which is used to
order them: their *timestamp*. This timestamp may simply be the time when the
entry was created: for example, a personal diary-type entry could use the time
when the user has recorded it as it's timestamp value. For file-based entries
like photos, this timestamp is extracted out of it's metadata. By populating
the timeline with entries (which can come from different sources, but are always
connected to exactly one library), users can browse their personal history,
consisting of different types of entries.

Entry querying
--------------

When using the API, you can obtain a simple list of timeline entries for the
current user like this:

.. code-block:: graphql

  query {
    timeline {
      entries(first: 10) {
        edges {
          node {
            id
            timestamp
            visibility
          }
        }
      }
    }
  }

Visibility
----------

Every timeline entry also has another interesting property: its *visibility*.
This is directly inherited from the generic
:ref:`library content <guide-library-content>` type. Depending on an entry's
visibility, it will show up in certain user's (including those of anonymous
users) timeline queries. See the guide linked before for details on this
property's value and how to set it using the `organizeLibraryContent` mutation.
