niquests-cache
==============

.. include:: badges.rst

Cached :mod:`niquests` sessions with pluggable storage backends.

Example usage
-------------

The :func:`cached_session <niquests_cache.session.cached_session>` helper returns a
:class:`CachedSession <niquests_cache.session.CachedSession>` or
:class:`AsyncCachedSession <niquests_cache.session.AsyncCachedSession>` whose cache database is
``platformdirs.user_cache_path(app_name, appauthor=False) / 'http.sqlite'``. If you omit
``app_name``, ``niquests-cache`` is used. Only successful ``GET`` and ``HEAD`` responses are
stored; the default TTL is 10 minutes (``expire_after=`` on the helper, or per request—see
below).

Sync helper (default application name and TTL):

.. code-block:: python

   from niquests_cache import cached_session

   session = cached_session()
   response = session.get('https://httpbin.org/get')
   response.raise_for_status()

Custom ``app_name`` for ``platformdirs.user_cache_path``:

.. code-block:: python

   from niquests_cache import cached_session

   session = cached_session(app_name='my-application')
   response = session.get('https://httpbin.org/get')
   response.raise_for_status()

Plain niquests session with no caching:

.. code-block:: python

   from niquests_cache import cached_session

   session = cached_session(no_cache=True)

Construct ``CachedSession`` when you need an explicit cache name or backend:

.. code-block:: python

   from pathlib import Path

   from niquests_cache import CachedSession

   with CachedSession(cache_name=Path('.cache') / 'http') as session:
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

Or construct ``AsyncCachedSession`` directly:

.. code-block:: python

   import asyncio
   from pathlib import Path

   from niquests_cache import AsyncCachedSession

   async def main() -> None:
       async with AsyncCachedSession(cache_name=Path('.cache') / 'http') as session:
           response = await session.get('https://httpbin.org/get')
           response.raise_for_status()

   asyncio.run(main())

Pick a non-default backend by alias or instance:

.. code-block:: python

   from niquests_cache import CachedSession
   from niquests_cache.backends import FileCache, MemoryBackend

   # Built-in aliases: 'sqlite' (default), 'filesystem', 'memory'.
   session = CachedSession(backend='filesystem', cache_name='./fs-cache')

   # Or pass a backend instance directly.
   session = CachedSession(backend=MemoryBackend())

   # FileCache with a non-default serialiser:
   session = CachedSession(backend=FileCache('./fs-cache', serializer='pickle'))

To bypass the cache read for one request, pass ``force_refresh=True`` to ``request()``; to return
a synthesised ``504`` when no cached entry exists, pass ``only_if_cached=True``.

API reference
-------------

.. only:: html

   .. automodule:: niquests_cache.session
      :members:

   .. automodule:: niquests_cache.backends.base
      :members:

   .. automodule:: niquests_cache.backends.file
      :members:

   .. automodule:: niquests_cache.backends.memory
      :members:

   .. automodule:: niquests_cache.backends.sqlite
      :members:

   .. automodule:: niquests_cache.serializers
      :members:

   .. automodule:: niquests_cache.settings
      :members:

   .. automodule:: niquests_cache.typing
      :members:

   Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
