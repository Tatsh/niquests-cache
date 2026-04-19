"""Cache settings dataclass for :class:`~niquests_cache.CachedSession`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    import re

    from niquests_cache.typing import ExpireAfter, Serializer

__all__ = ('CacheSettings',)

_DEFAULT_IGNORED: tuple[str, ...] = ('Authorization', 'X-API-KEY', 'access_token', 'api_key')


@dataclass
class CacheSettings:
    """Mutable settings controlling :class:`~niquests_cache.CachedSession` behaviour."""

    allowable_codes: tuple[int, ...] = (200,)
    """HTTP status codes whose responses may be cached."""
    allowable_methods: tuple[str, ...] = ('GET', 'HEAD')
    """HTTP methods whose responses may be cached."""
    always_revalidate: bool = False
    """Stored for parity with :mod:`requests_cache`; not used."""
    autoclose: bool = True
    """Stored for parity with :mod:`requests_cache`; not used."""
    cache_control: bool = False
    """Honour ``Cache-Control`` response headers (currently stored, not enforced)."""
    content_root_key: str | None = None
    """Stored for parity with :mod:`requests_cache`; not used."""
    disabled: bool = False
    """Internal flag toggled by :meth:`CachedSession.cache_disabled`."""
    expire_after: ExpireAfter = -1
    """Default TTL; ``-1`` or ``None`` means never expire."""
    filter_fn: Callable[..., bool] | None = None
    """Predicate deciding whether a response should be cached."""
    ignored_parameters: tuple[str, ...] = _DEFAULT_IGNORED
    """Header / query-parameter names removed before computing the cache key."""
    key_fn: Callable[..., str] | None = None
    """Optional callable producing a custom cache key."""
    match_headers: bool | tuple[str, ...] = False
    """``False`` ignores headers; ``True`` includes all; iterable: only those names."""
    read_only: bool = False
    """If ``True``, never write to the cache."""
    serializer: Serializer | None = None
    """Resolved serialiser used by the session to encode and decode entries."""
    stale_if_error: bool | int = False
    """Stored for parity with :mod:`requests_cache`; not used."""
    urls_expire_after: Mapping[str | re.Pattern[str], ExpireAfter] | None = None
    """Per-URL-pattern TTL overrides."""
