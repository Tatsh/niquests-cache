# niquests-cache

<!-- WISWA-GENERATED-README:START -->

[![Python versions](https://img.shields.io/pypi/pyversions/niquests-cache.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/niquests-cache)](https://pypi.org/project/niquests-cache/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/niquests-cache)](https://github.com/Tatsh/niquests-cache/tags)
[![License](https://img.shields.io/github/license/Tatsh/niquests-cache)](https://github.com/Tatsh/niquests-cache/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/niquests-cache/v0.2.0/master)](https://github.com/Tatsh/niquests-cache/compare/v0.2.0...master)
[![CodeQL](https://github.com/Tatsh/niquests-cache/actions/workflows/codeql.yml/badge.svg)](https://github.com/Tatsh/niquests-cache/actions/workflows/codeql.yml)
[![QA](https://github.com/Tatsh/niquests-cache/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/niquests-cache/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/niquests-cache/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/niquests-cache/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/niquests-cache/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/niquests-cache?branch=master)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-blue?logo=dependabot)](https://github.com/dependabot)
[![Documentation Status](https://readthedocs.org/projects/niquests-cache/badge/?version=latest)](https://niquests-cache.readthedocs.org/?badge=latest)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/badge/uv-261230?logo=astral)](https://docs.astral.sh/uv/)
[![pytest](https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black)](https://docs.pytest.org/en/stable/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Downloads](https://static.pepy.tech/badge/niquests-cache/month)](https://pepy.tech/project/niquests-cache)
[![Stargazers](https://img.shields.io/github/stars/Tatsh/niquests-cache?logo=github&style=flat)](https://github.com/Tatsh/niquests-cache/stargazers)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Prettier](https://img.shields.io/badge/Prettier-black?logo=prettier)](https://prettier.io/)

[![@Tatsh](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor=did%3Aplc%3Auq42idtvuccnmtl57nsucz72&query=%24.followersCount&label=Follow+%40Tatsh&logo=bluesky&style=social)](https://bsky.app/profile/Tatsh.bsky.social)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Tatsh-black?logo=buymeacoffee)](https://buymeacoffee.com/Tatsh)
[![Libera.Chat](https://img.shields.io/badge/Libera.Chat-Tatsh-black?logo=liberadotchat)](irc://irc.libera.chat/Tatsh)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social)](https://hostux.social/@Tatsh)
[![Patreon](https://img.shields.io/badge/Patreon-Tatsh2-F96854?logo=patreon)](https://www.patreon.com/Tatsh2)

<!-- WISWA-GENERATED-README:STOP -->

Cached [niquests](https://niquests.readthedocs.io) sessions with pluggable storage backends.
SQLite is the default; filesystem and in-memory backends are also built in.

## Installation

```shell
pip install niquests-cache
```

## Example usage

The `cached_session()` helper returns a `CachedSession` or `AsyncCachedSession` whose cache
database is `platformdirs.user_cache_path(app_name, appauthor=False) / 'http.sqlite'`. If you
omit `app_name`, `niquests-cache` is used. Only successful `GET` and `HEAD` responses are
written; the default time-to-live is 10 minutes (`expire_after=` on the helper, or per-request—
see below).

Sync helper (default app name and TTL):

```python
from niquests_cache import cached_session

session = cached_session()
response = session.get('https://httpbin.org/get')
response.raise_for_status()
```

Custom application name for `user_cache_path`:

```python
from niquests_cache import cached_session

session = cached_session(app_name='my-application')
response = session.get('https://httpbin.org/get')
response.raise_for_status()
```

Plain niquests session with no caching:

```python
from niquests_cache import cached_session

session = cached_session(no_cache=True)
```

Construct `CachedSession` when you need an explicit cache name or TTL:

```python
from datetime import timedelta
from pathlib import Path

from niquests_cache import CachedSession

with CachedSession(cache_name=Path('.cache') / 'http',
                   expire_after=timedelta(hours=1)) as session:
    response = session.get('https://httpbin.org/get')
    response.raise_for_status()
```

Async helper (use an async context manager):

```python
import asyncio
from datetime import timedelta

from niquests_cache import cached_session

async def main() -> None:
    async with cached_session(aio=True, expire_after=timedelta(minutes=30)) as session:
        response = await session.get('https://httpbin.org/get')
        response.raise_for_status()

asyncio.run(main())
```

Or construct `AsyncCachedSession` directly:

```python
import asyncio
from datetime import timedelta
from pathlib import Path

from niquests_cache import AsyncCachedSession

async def main() -> None:
    async with AsyncCachedSession(cache_name=Path('.cache') / 'http',
                                  expire_after=timedelta(hours=1)) as session:
        response = await session.get('https://httpbin.org/get')
        response.raise_for_status()

asyncio.run(main())
```

## Choosing a backend

Pass `backend=` as one of the built-in aliases (`'sqlite'` (default), `'filesystem'`, `'memory'`)
or a `BaseBackend` instance:

```python
from niquests_cache import CachedSession
from niquests_cache.backends import FileCache, MemoryBackend

# Filesystem backend with custom cache directory:
session = CachedSession(backend='filesystem', cache_name='./fs-cache')

# In-memory (per-process) cache:
session = CachedSession(backend=MemoryBackend())

# FileCache with the pickle serializer (preserves binary content natively):
session = CachedSession(backend=FileCache('./fs-cache', serializer='pickle'))
```

The `AsyncCachedSession` uses [aiosqlite](https://github.com/omnilib/aiosqlite) for SQLite and
[anyio](https://anyio.readthedocs.io) for filesystem I/O so async requests do not block the event
loop.

## Per-request controls

`request()` accepts `expire_after`, `only_if_cached`, `refresh`, and `force_refresh` per call:

```python
# Bypass the cache read and replace any stored entry:
session.get('https://httpbin.org/get', force_refresh=True)

# Return a synthesised 504 if the entry is missing instead of going to the network:
session.get('https://httpbin.org/get', only_if_cached=True)

# Override the session-wide TTL for one request:
session.get('https://httpbin.org/get', expire_after=60)
```

## Cache key behaviour

By default the cache key is `sha256(method + url + '')` — request headers are not part of the
key. Pass `match_headers=True` to include all session/request headers, or
`match_headers=('Accept', 'Accept-Language')` to include only the listed names. Strip query-string
parameters from the key with `ignored_parameters=('access_token', ...)`. Provide a `key_fn=` to
replace key generation entirely.

## Settings

All session settings live on the mutable `session.settings` dataclass
(`niquests_cache.settings.CacheSettings`); change them at runtime, for example
`session.settings.expire_after = 360` or `session.settings.read_only = True`. Use
`with session.cache_disabled():` to suspend caching for a block.
