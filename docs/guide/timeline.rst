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

The above example also shows another property of timeline entries: their
*visibility*. This is an enum that denotes who can see the entry, where there
are five possibilities:

- **Public** entries are visible to everyone, even users that are not logged
  int.
- **Internal** entries can be seen by anyone who is logged in on the server.
- Entries marked with **member-only** can only be seen by users which are a
  member of the entry's library.
- For **owner-only** entries to be seen, the user must be an owner of the
  corresponding library (have write access).
- The last possibility is to unset this field on the entry itself. Then, the
  visibility is inferred by the library's *default visibility* setting.
