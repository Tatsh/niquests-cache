"""Shared :mod:`niquests` cached sessions (sync and async)."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from os import PathLike
from pathlib import Path
from time import time
from typing import Any, Literal, TypeAlias, cast, overload
import contextlib
import json
import logging

import niquests
import platformdirs

__all__ = ('CachedAsyncSession', 'CachedSession', 'cached_session')

log = logging.getLogger(__name__)

_DEFAULT_EXPIRE = timedelta(minutes=10)

StrPath: TypeAlias = str | PathLike[str]


def _cache_key(cache_dir: Path, method: str, url: str) -> Path:
    digest = sha256(f'{method} {url}'.encode()).hexdigest()
    return cache_dir / digest


def _response_from_cache_entry(data: dict[str, Any]) -> niquests.Response:
    resp = niquests.Response()
    resp.status_code = data['status_code']
    resp._content = data['content'].encode('utf-8')  # noqa: SLF001
    resp.headers.update(data['headers'])
    resp.url = data['url']
    resp.encoding = data.get('encoding', 'utf-8')
    return resp


def _try_read_cache(
    cache_path: Path,
    ttl: float,
    method: str,
    url: str,
) -> niquests.Response | None:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding='utf-8'))
        if time() - data['ts'] < ttl:
            log.debug('Cache hit: %s %s', method, url)
            return _response_from_cache_entry(data)
    except (json.JSONDecodeError, KeyError, OSError):
        log.debug('Failed to read cache entry: %s', cache_path, exc_info=True)
    return None


def _write_cache(cache_path: Path, resp: niquests.Response) -> None:
    with contextlib.suppress(OSError):  # pragma: no cover
        cache_path.write_text(
            json.dumps({
                'ts': time(),
                'status_code': resp.status_code,
                'content': resp.text or '',
                'headers': dict(resp.headers),
                'url': str(resp.url),
                'encoding': resp.encoding,
            }),
            encoding='utf-8',
        )


class CachedSession(niquests.Session):
    """A synchronous niquests session with simple filesystem response caching."""
    def __init__(
        self,
        cache_dir: StrPath,
        expire_after: timedelta = _DEFAULT_EXPIRE,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._cache_dir = Path(cache_dir)
        self._expire_seconds = expire_after.total_seconds()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_directory(self) -> Path:
        """Filesystem directory used for this session's response cache."""
        return self._cache_dir

    @property
    def expire_after_total_seconds(self) -> float:
        """Cache TTL in seconds for GET and HEAD responses."""
        return self._expire_seconds

    def request(  # type: ignore[override]  # ty: ignore[invalid-method-override]
        self,
        method: str,
        url: str,
        *,
        expire_after: float | None = None,
        **kwargs: Any,
    ) -> niquests.Response:
        """
        Send a request, returning a cached response when available.

        Parameters
        ----------
        method : str
            The HTTP method.
        url : str
            The URL.
        expire_after : float | None
            Override cache expiry for this request. Set to ``0`` to bypass the cache.
        **kwargs : Any
            Additional keyword arguments passed to the parent.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        bypass = expire_after == 0
        ttl = self._expire_seconds if expire_after is None else expire_after
        if method.upper() in {'GET', 'HEAD'} and not bypass:
            cache_path = _cache_key(self._cache_dir, method, url)
            hit = _try_read_cache(cache_path, ttl, method, url)
            if hit is not None:
                return hit
        resp = super().request(method, url, **kwargs)
        if method.upper() in {'GET', 'HEAD'} and resp.ok and not bypass:
            log.debug('Caching response: %s %s', method, url)
            _write_cache(_cache_key(self._cache_dir, method, url), resp)
        return resp


class CachedAsyncSession(niquests.AsyncSession):
    """An async niquests session with simple filesystem response caching."""
    def __init__(
        self,
        cache_dir: StrPath,
        expire_after: timedelta = _DEFAULT_EXPIRE,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._cache_dir = Path(cache_dir)
        self._expire_seconds = expire_after.total_seconds()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_directory(self) -> Path:
        """Filesystem directory used for this session's response cache."""
        return self._cache_dir

    @property
    def expire_after_total_seconds(self) -> float:
        """Cache TTL in seconds for GET and HEAD responses."""
        return self._expire_seconds

    async def request(  # type: ignore[override]  # ty: ignore[invalid-method-override]
        self,
        method: str,
        url: str,
        *,
        expire_after: float | None = None,
        **kwargs: Any,
    ) -> niquests.Response:
        """
        Send a request, returning a cached response when available.

        Parameters
        ----------
        method : str
            The HTTP method.
        url : str
            The URL.
        expire_after : float | None
            Override cache expiry for this request. Set to ``0`` to bypass the cache.
        **kwargs : Any
            Additional keyword arguments passed to the parent.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        bypass = expire_after == 0
        ttl = self._expire_seconds if expire_after is None else expire_after
        if method.upper() in {'GET', 'HEAD'} and not bypass:
            cache_path = _cache_key(self._cache_dir, method, url)
            hit = _try_read_cache(cache_path, ttl, method, url)
            if hit is not None:
                return hit
        resp = cast('niquests.Response', await super().request(method, url, **kwargs))
        if method.upper() in {'GET', 'HEAD'} and resp.ok and not bypass:
            log.debug('Caching response: %s %s', method, url)
            _write_cache(_cache_key(self._cache_dir, method, url), resp)
        return resp


@overload
def cached_session(
    *,
    aio: Literal[False] = ...,
    no_cache: Literal[True],
    app_name: str | None = ...,
    expire_after: timedelta = ...,
) -> niquests.Session:
    ...


@overload
def cached_session(
    *,
    aio: Literal[True],
    no_cache: Literal[True],
    app_name: str | None = ...,
    expire_after: timedelta = ...,
) -> niquests.AsyncSession:
    ...


@overload
def cached_session(
    *,
    aio: Literal[True],
    no_cache: Literal[False] = ...,
    app_name: str | None = ...,
    expire_after: timedelta = ...,
) -> CachedAsyncSession:
    ...


@overload
def cached_session(
    *,
    aio: Literal[False] = ...,
    no_cache: Literal[False] = ...,
    app_name: str | None = ...,
    expire_after: timedelta = ...,
) -> CachedSession:
    ...


# For the following cases it is impossible to know which type will be returned, so only return the
# parent classes.


@overload
def cached_session(
    *,
    aio: Literal[False] = ...,
    no_cache: bool = ...,
    app_name: str | None = ...,
    expire_after: timedelta = ...,
) -> niquests.Session:
    ...


@overload
def cached_session(
    *,
    aio: Literal[True],
    no_cache: bool = ...,
    app_name: str | None = ...,
    expire_after: timedelta = ...,
) -> niquests.AsyncSession:
    ...


def cached_session(
    *,
    aio: bool = False,
    no_cache: bool = False,
    app_name: str | None = None,
    expire_after: timedelta = _DEFAULT_EXPIRE,
) -> niquests.Session | niquests.AsyncSession | CachedSession | CachedAsyncSession:
    """
    Get a niquests session, optionally with filesystem caching.

    Parameters
    ----------
    aio : bool
        If ``True``, return an async session; otherwise a synchronous session.
    no_cache : bool
        If ``True``, return a plain session without caching.
    app_name : str | None
        First argument to :func:`platformdirs.user_cache_path` for the cache root. If ``None``,
        uses ``niquests-cache``. Cached entries live under ``<user cache path> / 'http'``.
    expire_after : timedelta
        Cache expiry duration (ignored when ``no_cache`` is ``True``).

    Returns
    -------
    CachedSession | CachedAsyncSession | niquests.Session | niquests.AsyncSession
        A plain :py:class:`~niquests.Session` or :py:class:`~niquests.AsyncSession`
        when ``no_cache`` is ``True`` (depending on ``aio``); otherwise a
        :py:class:`CachedSession` or :py:class:`CachedAsyncSession`. Use an async
        context manager when ``aio`` is ``True``.
    """
    if no_cache:
        return niquests.AsyncSession() if aio else niquests.Session()
    cache_dir = platformdirs.user_cache_path('niquests-cache' if app_name is None else app_name,
                                             appauthor=False,
                                             ensure_exists=True) / 'http'
    if aio:
        return CachedAsyncSession(cache_dir=cache_dir, expire_after=expire_after)
    return CachedSession(cache_dir=cache_dir, expire_after=expire_after)
