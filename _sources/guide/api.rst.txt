.. _guide-api:

Connecting to the API
=====================

Tumpara exposes a `GraphQL`_-based API. This is the main and preferred way for
clients to interact with the server. If you find that it is missing something,
please open an issue.

.. _GraphQL: https://graphql.org/

GraphQL is an API design language that gives clients a *schema* to explore. This
schema contains everything about the server's data structure and allows clients
to request exactly the data they need. Tumpara exposes this API under
``/api/graphql``. Since GraphQL also serves documentation for the schema, you
can visit this URL in the browser and browse the API for yourself and also try
out some queries.

.. note::
  The API currently uses the same authentication as the admin backend. Whenever
  you are logged in to the admin site, GraphQL queries will return data for that
  user. This will probably change to use something like API keys in the future.
  It also means that the API needs to be hosted under that same domain as any
  web-based clients in order for session cookies to be transmitted.

As an example, try the following query in the GraphQL browser to get information
about the currently active user:

.. code-block:: graphql

  query {
    me {
      username
      email
    }
  }

There are a bunch of different GraphQL clients for various languages, see
`this list`_ for an overview. When writing a client, this is probably the best
choice as many of these libraries enable more features on top of a mere request
client such as caching or batching. However, if you only need a few queries or
don't rely on those features, it will be less overhead to use any available HTTP
client. For example, the above query can also be executed with regular ``curl``:

.. _this list: https://graphql.org/code/

.. code-block:: shell

  curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "{ me { username email } }"}' \
  http://localhost:8000/graphql

For a more in-depth guide on this topic, see the `documentation`_ on the GraphQL
project's website.

.. _documentation: https://graphql.org/graphql-js/graphql-clients/
