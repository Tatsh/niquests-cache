niquests-cache
==============

.. include:: badges.rst

Filesystem-cached niquests sessions.

Example usage
-------------

The :func:`cached_session <niquests_cache.session.cached_session>` helper returns a
:class:`CachedSession <niquests_cache.session.CachedSession>` or
:class:`CachedAsyncSession <niquests_cache.session.CachedAsyncSession>` whose cache root is
``platformdirs.user_cache_path(app_name, appauthor=False) / 'http'``. If you omit ``app_name``,
``niquests-cache`` is used. Only successful ``GET`` and ``HEAD`` responses are stored; the
default TTL is 10 minutes (``expire_after=`` on the helper, or per request—see below).

Sync helper (default application name and TTL):

.. code-block:: python

   from niquests_cache import cached_session

   session = cached_session()
   response = session.get('https://httpbin.org/get')
   response.raise_for_status()

Custom ``app_name`` for ``platformdirs.user_cache_path`` (same ``http`` subdirectory):

.. code-block:: python

   from niquests_cache import cached_session

   session = cached_session(app_name='my-application')
   response = session.get('https://httpbin.org/get')
   response.raise_for_status()

Plain niquests session with no filesystem cache:

.. code-block:: python

   from niquests_cache import cached_session

   session = cached_session(no_cache=True)

Construct ``CachedSession`` when you need an explicit directory:

.. code-block:: python

   from pathlib import Path

   from niquests_cache import CachedSession

   cache = Path('.cache') / 'http'
   with CachedSession(cache_dir=cache) as session:
       response = session.get('https://httpbin.org/get')
       response.raise_for_status()

Async helper (async context manager):

.. code-block:: python

   import asyncio
   from datetime import timedelta

   from niquests_cache import cached_session

   async def main() -> None:
       async with cached_session(aio=True, expire_after=timedelta(minutes=30)) as session:
           response = await session.get('https://httpbin.org/get')
           response.raise_for_status()

   asyncio.run(main())

Or construct ``CachedAsyncSession`` directly:

.. code-block:: python

   import asyncio
   from datetime import timedelta
   from pathlib import Path

   from niquests_cache import CachedAsyncSession

   async def main() -> None:
       cache = Path('.cache') / 'http'
       async with CachedAsyncSession(cache_dir=cache, expire_after=timedelta(hours=1)) as session:
           response = await session.get('https://httpbin.org/get')
           response.raise_for_status()

   asyncio.run(main())

To bypass the cache for one request, pass ``expire_after=0`` to ``request`` (that ``GET`` or
``HEAD`` is not read from or written to the cache).

.. only:: html

   .. automodule:: niquests_cache.session
      :members:

   Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
