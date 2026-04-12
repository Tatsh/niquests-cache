# niquests-cache

<!-- WISWA-GENERATED-README:START -->

[![Python versions](https://img.shields.io/pypi/pyversions/niquests-cache.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/niquests-cache)](https://pypi.org/project/niquests-cache/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/niquests-cache)](https://github.com/Tatsh/niquests-cache/tags)
[![License](https://img.shields.io/github/license/Tatsh/niquests-cache)](https://github.com/Tatsh/niquests-cache/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/niquests-cache/v0.0.0/master)](https://github.com/Tatsh/niquests-cache/compare/v0.0.0...master)
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
[![pre-commit](https://img.shields.io/badge/pre--commit-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Prettier](https://img.shields.io/badge/Prettier-black?logo=prettier)](https://prettier.io/)

[![@Tatsh](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor=did%3Aplc%3Auq42idtvuccnmtl57nsucz72&query=%24.followersCount&label=Follow+%40Tatsh&logo=bluesky&style=social)](https://bsky.app/profile/Tatsh.bsky.social)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Tatsh-black?logo=buymeacoffee)](https://buymeacoffee.com/Tatsh)
[![Libera.Chat](https://img.shields.io/badge/Libera.Chat-Tatsh-black?logo=liberadotchat)](irc://irc.libera.chat/Tatsh)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social)](https://hostux.social/@Tatsh)
[![Patreon](https://img.shields.io/badge/Patreon-Tatsh2-F96854?logo=patreon)](https://www.patreon.com/Tatsh2)

<!-- WISWA-GENERATED-README:STOP -->

Filesystem-cached niquests sessions.

## Installation

```shell
pip install niquests-cache
```

## Example usage

The `cached_session()` helper returns a `CachedSession` or `CachedAsyncSession` whose cache root
is `platformdirs.user_cache_path(app_name, appauthor=False) / 'http'`. If you omit `app_name`,
`niquests-cache` is used. Only successful `GET` and `HEAD` responses are written to disk; the
default time-to-live is 10 minutes (`expire_after=` on the helper, or per-request—see below).

Sync helper (default app name and TTL):

```python
from niquests_cache import cached_session

session = cached_session()
response = session.get('https://httpbin.org/get')
response.raise_for_status()
```

Custom application name for `user_cache_path` (same `http` subdirectory):

```python
from niquests_cache import cached_session

session = cached_session(app_name='my-application')
response = session.get('https://httpbin.org/get')
response.raise_for_status()
```

Plain niquests session with no filesystem cache:

```python
from niquests_cache import cached_session

session = cached_session(no_cache=True)
```

Construct `CachedSession` when you need an explicit directory or TTL:

```python
from datetime import timedelta
from pathlib import Path

from niquests_cache import CachedSession

cache = Path('.cache') / 'http'
with CachedSession(cache_dir=cache, expire_after=timedelta(hours=1)) as session:
    response = session.get('https://httpbin.org/get')
    response.raise_for_status()
```

Async helper (use an async context manager):

```python
import asyncio
from datetime import timedelta

from niquests_cache import cached_session

async def main() -> None:
    session = cached_session(aio=True, expire_after=timedelta(minutes=30))
    async with session:
        response = await session.get('https://httpbin.org/get')
        response.raise_for_status()

asyncio.run(main())
```

Or construct `CachedAsyncSession` directly:

```python
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
```

To bypass the cache for a single request, pass `expire_after=0` to `request` (that `GET` or
`HEAD` is not served from or written to the cache).
