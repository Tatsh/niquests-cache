"""Cached :mod:`niquests` sessions matching :class:`requests_cache.CachedSession`'s API."""
from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from http import HTTPStatus
from time import time
from typing import TYPE_CHECKING, Any, Literal, cast, overload
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import contextlib
import json
import logging
import re

from niquests_cache.backends import BaseBackend, FileCache, MemoryBackend, SQLiteBackend
from niquests_cache.serializers import resolve_serializer
from niquests_cache.settings import CacheSettings
from typing_extensions import override
import niquests
import platformdirs

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable, Iterator, Mapping

    from niquests_cache.backends.file import StrPath
    from niquests_cache.typing import BackendAlias, CacheEntry, ExpireAfter, Serializer

__all__ = ('AsyncCachedSession', 'CacheMixin', 'CachedSession', 'cached_session')

log = logging.getLogger(__name__)

_INF = float('inf')
_DEFAULT_IGNORED: tuple[str, ...] = ('Authorization', 'If-Modified-Since', 'If-None-Match',
                                     'X-API-KEY', 'access_token', 'api_key')
_DEFAULT_HELPER_TTL = timedelta(minutes=10)
_CACHE_ONLY_REQUEST_KWARGS: tuple[str, ...] = ('expire_after', 'force_refresh', 'only_if_cached',
                                               'refresh')


def _lookup_header(headers: Mapping[str, Any], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return str(value) if value is not None else None
    return None


def _attach_validators(entry: CacheEntry, kwargs: dict[str, Any]) -> bool:
    """
    Copy ``ETag`` / ``Last-Modified`` validators from *entry* into *kwargs*' headers.

    Parameters
    ----------
    entry : CacheEntry
        The stored cache entry.
    kwargs : dict[str, Any]
        The outbound request kwargs, mutated in place.

    Returns
    -------
    bool
        ``True`` if any conditional header was attached.
    """
    stored_headers = entry.get('headers') or {}
    etag = _lookup_header(stored_headers, 'etag')
    last_modified = _lookup_header(stored_headers, 'last-modified')
    if not etag and not last_modified:
        return False
    headers = dict(kwargs.get('headers') or {})
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    kwargs['headers'] = headers
    return True


def _to_seconds(value: ExpireAfter) -> float:
    """
    Coerce an ``expire_after`` value to seconds.

    Parameters
    ----------
    value : ExpireAfter
        The value to coerce. ``None`` and ``-1`` mean never expire.

    Returns
    -------
    float
        The TTL in seconds; :py:data:`math.inf` means never expire.

    Raises
    ------
    TypeError
        If the value type is unsupported.
    """
    if value is None:
        return _INF
    if isinstance(value, bool):
        msg = 'expire_after may not be a bool.'
        raise TypeError(msg)
    if isinstance(value, int | float):
        return _INF if value == -1 else float(value)
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, datetime):
        now = datetime.now(tz=value.tzinfo)
        return max(0.0, (value - now).total_seconds())
    msg = f'Unsupported expire_after type: {type(value).__name__}.'
    raise TypeError(msg)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    return re.compile(re.escape(pattern).replace(r'\*', '.*').replace(r'\?', '.'))


def _resolve_url_ttl(url: str, mapping: Mapping[str | re.Pattern[str],
                                                ExpireAfter]) -> float | None:
    for pattern, value in mapping.items():
        compiled = pattern if isinstance(pattern, re.Pattern) else _glob_to_regex(pattern)
        if compiled.search(url):
            return _to_seconds(value)
    return None


def _backend_from_alias(alias: str,
                        cache_name: StrPath,
                        serializer: Serializer | str | None = None) -> BaseBackend:
    name = str(cache_name)
    match alias:
        case 'filesystem':
            return FileCache(cache_name, serializer=serializer)
        case 'sqlite':
            return SQLiteBackend(name if name == ':memory:' else f'{name}.sqlite')
        case 'memory':
            return MemoryBackend()
        case _:
            msg = f'Unknown backend alias: {alias!r}.'
            raise ValueError(msg)


def _filter_query(url: str, ignored: Iterable[str]) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url
    ignored_lower = {p.lower() for p in ignored}
    kept = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in ignored_lower]
    return urlunparse(parsed._replace(query=urlencode(kept)))


def _merge_headers(session_headers: Mapping[str, Any],
                   extra: Mapping[str, Any] | None) -> dict[str, str]:
    merged = {k: str(v) for k, v in session_headers.items() if v is not None}
    if extra:
        for k, v in extra.items():
            if v is None:
                merged.pop(k, None)
                continue
            merged[k] = str(v)
    return merged


def _select_headers(headers: Mapping[str, str], *, match: bool | tuple[str, ...],
                    ignored: Iterable[str]) -> Mapping[str, str] | None:
    if match is False:
        return None
    ignored_lower = {p.lower() for p in ignored}
    if match is True:
        return {k: v for k, v in headers.items() if k.lower() not in ignored_lower}
    allowed = {h.lower() for h in match}
    return {
        k: v
        for k, v in headers.items() if k.lower() in allowed and k.lower() not in ignored_lower
    }


def _canonical_headers(headers: Mapping[str, str] | None) -> str:
    if not headers:
        return ''
    return json.dumps(sorted((k.lower(), str(v)) for k, v in headers.items()),
                      separators=(',', ':'))


def _default_key(method: str, url: str, headers: Mapping[str, str] | None) -> str:
    return sha256(f'{method} {url} {_canonical_headers(headers)}'.encode()).hexdigest()


def _response_from_entry(data: CacheEntry) -> niquests.Response:
    resp = niquests.Response()
    resp.status_code = data['status_code']
    resp._content = data['content']  # noqa: SLF001
    resp.headers.update(data['headers'])
    resp.url = data['url']
    resp.encoding = data.get('encoding', 'utf-8')
    return resp


def _entry_from_response(resp: niquests.Response) -> CacheEntry:
    raw_headers = cast('dict[str, str | bytes]', dict(resp.headers))
    return {
        'content': resp.content or b'',
        'encoding': resp.encoding or 'utf-8',
        'headers': {
            k: v if isinstance(v, str) else v.decode()
            for k, v in raw_headers.items()
        },
        'status_code': resp.status_code or 0,
        'ts': time(),
        'url': str(resp.url)
    }


def _log_backend(backend: BaseBackend) -> None:
    cls = type(backend)
    name = f'{cls.__module__}.{cls.__qualname__}'
    path = getattr(backend, 'cache_dir', None) or getattr(backend, 'database', None)
    log.debug('Using backend `%s`.%s', name, f' Path: {path}' if path else '')


def _resolve_backend(backend: BaseBackend | BackendAlias | None,
                     cache_name: StrPath,
                     serializer: Serializer | str | None = None) -> BaseBackend:
    if backend is None:
        return _backend_from_alias('sqlite', cache_name, serializer)
    if isinstance(backend, str):
        return _backend_from_alias(backend, cache_name, serializer)
    return backend


def _make_504(url: str) -> niquests.Response:
    resp = niquests.Response()
    resp.status_code = 504
    resp._content = b''  # noqa: SLF001
    resp.url = url
    resp.encoding = 'utf-8'
    return resp


def _resolve_ttl(url: str, expire_after: ExpireAfter, settings: CacheSettings) -> float:
    if expire_after is not None:
        return _to_seconds(expire_after)
    if settings.urls_expire_after:
        match = _resolve_url_ttl(url, settings.urls_expire_after)
        if match is not None:
            return match
    return _to_seconds(settings.expire_after)


def _build_key(method: str, url: str, kwargs: Mapping[str, Any], session_headers: Mapping[str, Any],
               settings: CacheSettings) -> str:
    eff_url = _filter_query(url, settings.ignored_parameters)
    eff_headers = _select_headers(_merge_headers(session_headers, kwargs.get('headers')),
                                  match=settings.match_headers,
                                  ignored=settings.ignored_parameters)
    if settings.key_fn is not None:
        result: str = settings.key_fn(method=method, url=eff_url, headers=eff_headers)
        return result
    return _default_key(method, eff_url, eff_headers)


def _try_cache_hit(entry: CacheEntry, ttl: float, method: str,
                   url: str) -> niquests.Response | None:
    try:
        if ttl == _INF or time() - entry['ts'] < ttl:
            log.debug('Cache hit: %s %s', method, url)
            return _response_from_entry(entry)
    except KeyError:
        log.debug('Malformed cache entry: %s %s', method, url, exc_info=True)
    return None


def _should_store(method: str, resp: niquests.Response, settings: CacheSettings) -> bool:
    # A streamed response (``stream=True``) whose body the caller has not yet read cannot be
    # cached: in async mode ``resp.content`` is still a coroutine at this point, so materialising
    # the cache entry would bind an unresolved coroutine into the backend.
    if not getattr(resp, '_content_consumed', True):
        return False
    return (resp.status_code in settings.allowable_codes and method in settings.allowable_methods
            and (settings.filter_fn is None or settings.filter_fn(resp)) and not settings.read_only)


class CacheMixin:
    """Shared state and helpers between sync and async cached sessions."""
    def __init__(self,
                 cache_name: StrPath = 'http_cache',
                 backend: BaseBackend | BackendAlias | None = None,
                 *,
                 serializer: Serializer | str | None = None,
                 expire_after: ExpireAfter = -1,
                 urls_expire_after: Mapping[str | re.Pattern[str], ExpireAfter] | None = None,
                 cache_control: bool = False,
                 content_root_key: str | None = None,
                 allowable_codes: Iterable[int] = (200,),
                 allowable_methods: Iterable[str] = ('GET', 'HEAD'),
                 always_revalidate: bool = False,
                 ignored_parameters: Iterable[str] = _DEFAULT_IGNORED,
                 match_headers: bool | Iterable[str] = False,
                 filter_fn: Callable[..., bool] | None = None,
                 key_fn: Callable[..., str] | None = None,
                 read_only: bool = False,
                 stale_if_error: bool | int = False,
                 autoclose: bool = True,
                 **kwargs: Any) -> None:
        """
        Initialise the cache mixin with backend and settings.

        Parameters
        ----------
        cache_name : StrPath
            Base name or path for the cache storage.
        backend : BaseBackend | BackendAlias | None
            Storage backend instance, an alias string (``'sqlite'``, ``'filesystem'``,
            ``'memory'``), or ``None`` to default to SQLite.
        serializer : Serializer | str | None
            Serialiser to use for reading and writing cache entries.
        expire_after : ExpireAfter
            Default time-to-live for cache entries. ``-1`` means never expire.
        urls_expire_after : Mapping[str | re.Pattern[str], ExpireAfter] | None
            Per-URL pattern overrides for cache expiry.
        cache_control : bool
            If ``True``, honour ``ETag`` and ``Last-Modified`` revalidation headers.
        content_root_key : str | None
            Reserved for future use.
        allowable_codes : Iterable[int]
            HTTP status codes eligible for caching.
        allowable_methods : Iterable[str]
            HTTP methods eligible for caching.
        always_revalidate : bool
            If ``True``, always send a conditional request even on a cache hit.
        ignored_parameters : Iterable[str]
            Header and query-string parameter names excluded from the cache key.
        match_headers : bool | Iterable[str]
            Whether to include request headers in the cache key. ``True`` includes
            all headers; a sequence includes only the listed names.
        filter_fn : Callable[..., bool] | None
            Optional predicate; responses for which it returns ``False`` are not cached.
        key_fn : Callable[..., str] | None
            Optional custom cache-key generator replacing the default.
        read_only : bool
            If ``True``, the cache is never written to.
        stale_if_error : bool | int
            Serve stale entries on upstream errors; an ``int`` sets the grace period
            in seconds.
        autoclose : bool
            If ``True``, the backend is closed when the session is closed.
        **kwargs : Any
            Additional keyword arguments forwarded to the parent session class.
        """
        super().__init__(**kwargs)
        self._cache: BaseBackend = _resolve_backend(backend, cache_name, serializer)
        _log_backend(self._cache)
        self.settings: CacheSettings = CacheSettings(
            allowable_codes=tuple(allowable_codes),
            allowable_methods=tuple(m.upper() for m in allowable_methods),
            always_revalidate=always_revalidate,
            autoclose=autoclose,
            cache_control=cache_control,
            content_root_key=content_root_key,
            expire_after=expire_after,
            filter_fn=filter_fn,
            ignored_parameters=tuple(ignored_parameters),
            key_fn=key_fn,
            match_headers=(match_headers
                           if isinstance(match_headers, bool) else tuple(match_headers)),
            read_only=read_only,
            serializer=resolve_serializer(serializer),
            stale_if_error=stale_if_error,
            urls_expire_after=urls_expire_after)
        """Mutable cache settings for this session."""

    @property
    def cache(self) -> BaseBackend:
        """The storage backend in use."""
        return self._cache

    @property
    def backend(self) -> BaseBackend:
        """Alias for :attr:`cache`."""
        return self._cache


class CachedSession(CacheMixin, niquests.Session):
    """Synchronous cached :mod:`niquests` session."""
    @contextlib.contextmanager
    def cache_disabled(self) -> Iterator[None]:
        """
        Temporarily disable caching for the duration of the ``with`` block.

        Yields
        ------
        None
            Control returns to the caller while caching is disabled.
        """
        prev = self.settings.disabled
        self.settings.disabled = True
        try:
            yield
        finally:
            self.settings.disabled = prev

    def request(  # type: ignore[override]
            self,
            method: str,
            url: str,
            *args: Any,
            headers: Mapping[str, str] | None = None,
            expire_after: ExpireAfter = None,
            only_if_cached: bool = False,
            refresh: bool = False,
            force_refresh: bool = False,
            **kwargs: Any) -> niquests.Response:
        """
        Send a request, returning a cached response when one is available.

        Parameters
        ----------
        method : str
            The HTTP method.
        url : str
            The URL.
        *args : Any
            Positional arguments forwarded to the parent.
        headers : Mapping[str, str] | None
            Per-request headers.
        expire_after : ExpireAfter
            Per-request override of the cache expiry.
        only_if_cached : bool
            If ``True``, return a synthesised ``504`` when the entry is missing.
        refresh : bool
            Currently treated like ``force_refresh``; reserved for revalidation.
        force_refresh : bool
            If ``True``, bypass the cache read and replace the stored entry.
        **kwargs : Any
            Additional keyword arguments forwarded to the parent.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        if headers is not None:
            kwargs['headers'] = headers
        s = self.settings
        method_upper = method.upper()
        bypass_read = force_refresh or refresh
        if s.disabled or method_upper not in s.allowable_methods:
            return super().request(method, url, *args, **kwargs)
        key = _build_key(method_upper, url, kwargs, self.headers, s)
        ttl = _resolve_ttl(url, expire_after, s)
        entry = None if bypass_read else self._cache.get(key)
        if entry is not None and not s.always_revalidate and ttl > 0 and (hit := _try_cache_hit(
                entry, ttl, method_upper, url)) is not None:
            return hit
        if only_if_cached:
            return _make_504(url)
        if entry is not None and s.cache_control:
            _attach_validators(entry, kwargs)
        resp = super().request(method, url, *args, **kwargs)
        if resp.status_code == HTTPStatus.NOT_MODIFIED.value and entry is not None:
            log.debug('304 Not Modified: refreshing cache entry for %s %s.', method_upper, url)
            entry['ts'] = time()
            self._cache.set(key, entry)
            return _response_from_entry(entry)
        if _should_store(method_upper, resp, s):
            log.debug('Caching response: %s %s', method, url)
            self._cache.set(key, _entry_from_response(resp))
        return resp


class AsyncCachedSession(CacheMixin, niquests.AsyncSession):
    """Asynchronous cached :mod:`niquests` session."""
    @contextlib.asynccontextmanager
    async def cache_disabled(self) -> AsyncIterator[None]:
        """
        Temporarily disable caching for the duration of the ``async with`` block.

        Yields
        ------
        None
            Control returns to the caller while caching is disabled.
        """
        prev = self.settings.disabled
        self.settings.disabled = True
        try:
            yield
        finally:
            self.settings.disabled = prev

    async def request(  # type: ignore[override] # ty: ignore[invalid-method-override]
            self,
            method: str,
            url: str,
            *args: Any,
            headers: Mapping[str, str] | None = None,
            expire_after: ExpireAfter = None,
            only_if_cached: bool = False,
            refresh: bool = False,
            force_refresh: bool = False,
            **kwargs: Any) -> niquests.Response:
        """
        Send an async request, returning a cached response when available.

        Parameters
        ----------
        method : str
            The HTTP method.
        url : str
            The URL.
        *args : Any
            Positional arguments forwarded to the parent.
        headers : Mapping[str, str] | None
            Per-request headers.
        expire_after : ExpireAfter
            Per-request override of the cache expiry.
        only_if_cached : bool
            If ``True``, return a synthesised ``504`` when the entry is missing.
        refresh : bool
            Currently treated like ``force_refresh``; reserved for revalidation.
        force_refresh : bool
            If ``True``, bypass the cache read and replace the stored entry.
        **kwargs : Any
            Additional keyword arguments forwarded to the parent.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        if headers is not None:
            kwargs['headers'] = headers
        s = self.settings
        method_upper = method.upper()
        bypass_read = force_refresh or refresh
        if s.disabled or method_upper not in s.allowable_methods:
            return cast('niquests.Response', await super().request(method, url, *args, **kwargs))
        key = _build_key(method_upper, url, kwargs, self.headers, s)
        ttl = _resolve_ttl(url, expire_after, s)
        entry = None if bypass_read else await self._cache.aget(key)
        if entry is not None and not s.always_revalidate and ttl > 0 and (hit := _try_cache_hit(
                entry, ttl, method_upper, url)) is not None:
            return hit
        if only_if_cached:
            return _make_504(url)
        if entry is not None and s.cache_control:
            _attach_validators(entry, kwargs)
        resp = cast('niquests.Response', await super().request(method, url, *args, **kwargs))
        if resp.status_code == HTTPStatus.NOT_MODIFIED.value and entry is not None:
            log.debug('304 Not Modified: refreshing cache entry for %s %s.', method_upper, url)
            entry['ts'] = time()
            await self._cache.aset(key, entry)
            return _response_from_entry(entry)
        if _should_store(method_upper, resp, s):
            log.debug('Caching response: %s %s', method, url)
            await self._cache.aset(key, _entry_from_response(resp))
        return resp


class _NoCacheSession(niquests.Session):
    """
    Plain :class:`niquests.Session` that silently ignores cache-only request kwargs.

    Returned by :func:`cached_session` when ``no_cache`` is ``True`` so callers can pass
    ``expire_after``, ``only_if_cached``, ``refresh``, or ``force_refresh`` without raising
    :py:class:`TypeError`.
    """
    @override
    def request(self, method: str, url: str, *args: Any, **kwargs: Any) -> niquests.Response:
        """
        Send a request, dropping cache-only kwargs before delegating to the parent.

        Parameters
        ----------
        method : str
            The HTTP method.
        url : str
            The URL.
        *args : Any
            Positional arguments forwarded to :py:meth:`niquests.Session.request`.
        **kwargs : Any
            Keyword arguments forwarded to :py:meth:`niquests.Session.request`. Cache-only keys
            (``expire_after``, ``only_if_cached``, ``refresh``, ``force_refresh``) are removed.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        for k in _CACHE_ONLY_REQUEST_KWARGS:
            kwargs.pop(k, None)
        return super().request(method, url, *args, **kwargs)


class _NoCacheAsyncSession(niquests.AsyncSession):
    """
    Plain :class:`niquests.AsyncSession` that silently ignores cache-only request kwargs.

    Returned by :func:`cached_session` when ``no_cache`` is ``True`` and ``aio`` is ``True`` so
    callers can pass ``expire_after``, ``only_if_cached``, ``refresh``, or ``force_refresh``
    without raising :py:class:`TypeError`.
    """
    @override
    async def request(  # type: ignore[override]
            self, method: str, url: str, *args: Any, **kwargs: Any) -> niquests.Response:
        """
        Send an async request, dropping cache-only kwargs before delegating to the parent.

        Parameters
        ----------
        method : str
            The HTTP method.
        url : str
            The URL.
        *args : Any
            Positional arguments forwarded to :py:meth:`niquests.AsyncSession.request`.
        **kwargs : Any
            Keyword arguments forwarded to :py:meth:`niquests.AsyncSession.request`. Cache-only
            keys (``expire_after``, ``only_if_cached``, ``refresh``, ``force_refresh``) are
            removed.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        for k in _CACHE_ONLY_REQUEST_KWARGS:
            kwargs.pop(k, None)
        return cast('niquests.Response', await super().request(method, url, *args, **kwargs))


@overload
def cached_session(*,
                   aio: Literal[False] = ...,
                   no_cache: Literal[True],
                   app_name: str | None = ...,
                   backend: BaseBackend | BackendAlias | None = ...,
                   expire_after: timedelta = ...) -> niquests.Session:
    ...


@overload
def cached_session(*,
                   aio: Literal[True],
                   no_cache: Literal[True],
                   app_name: str | None = ...,
                   backend: BaseBackend | BackendAlias | None = ...,
                   expire_after: timedelta = ...) -> niquests.AsyncSession:
    ...


@overload
def cached_session(*,
                   aio: Literal[True],
                   no_cache: Literal[False] = ...,
                   app_name: str | None = ...,
                   backend: BaseBackend | BackendAlias | None = ...,
                   expire_after: timedelta = ...) -> AsyncCachedSession:
    ...


@overload
def cached_session(*,
                   aio: Literal[False] = ...,
                   no_cache: Literal[False] = ...,
                   app_name: str | None = ...,
                   backend: BaseBackend | BackendAlias | None = ...,
                   expire_after: timedelta = ...) -> CachedSession:
    ...


@overload
def cached_session(*,
                   aio: Literal[False] = ...,
                   no_cache: bool = ...,
                   app_name: str | None = ...,
                   backend: BaseBackend | BackendAlias | None = ...,
                   expire_after: timedelta = ...) -> niquests.Session:
    ...


@overload
def cached_session(*,
                   aio: Literal[True],
                   no_cache: bool = ...,
                   app_name: str | None = ...,
                   backend: BaseBackend | BackendAlias | None = ...,
                   expire_after: timedelta = ...) -> niquests.AsyncSession:
    ...


def cached_session(
    *,
    aio: bool = False,
    no_cache: bool = False,
    app_name: str | None = None,
    backend: BaseBackend | BackendAlias | None = None,
    expire_after: timedelta = _DEFAULT_HELPER_TTL
) -> niquests.Session | niquests.AsyncSession | CachedSession | AsyncCachedSession:
    """
    Get a niquests session, optionally with SQLite-backed caching.

    The default cache database lives at ``<user cache path>/http.sqlite``.

    Parameters
    ----------
    aio : bool
        If ``True``, return an async session; otherwise a synchronous session.
    no_cache : bool
        If ``True``, return a plain session without caching.
    app_name : str | None
        First argument to :func:`platformdirs.user_cache_path` for the cache root. If ``None``,
        uses ``niquests-cache``.
    backend : BaseBackend | BackendAlias | None
        Storage backend. May be a :class:`BaseBackend` instance, an alias (``'sqlite'``,
        ``'filesystem'``, ``'memory'``), or ``None`` (default) to use SQLite at the user-cache
        path derived from ``app_name``.
    expire_after : timedelta
        Cache expiry duration (ignored when ``no_cache`` is ``True``).

    Returns
    -------
    CachedSession | AsyncCachedSession | niquests.Session | niquests.AsyncSession
        A plain :py:class:`~niquests.Session` or :py:class:`~niquests.AsyncSession`
        when ``no_cache`` is ``True`` (depending on ``aio``); otherwise a
        :py:class:`CachedSession` or :py:class:`AsyncCachedSession`. Use an async
        context manager when ``aio`` is ``True``.
    """
    if no_cache:
        return _NoCacheAsyncSession() if aio else _NoCacheSession()
    cache_name = platformdirs.user_cache_path('niquests-cache' if app_name is None else app_name,
                                              appauthor=False,
                                              ensure_exists=True) / 'http'
    cls = AsyncCachedSession if aio else CachedSession
    return cls(cache_name=cache_name,
               backend=backend,
               expire_after=expire_after,
               match_headers=True)
