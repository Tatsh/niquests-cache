"""Filesystem cache backend matching the :class:`requests_cache.FileCache` public API."""
from __future__ import annotations

from contextlib import nullcontext
from os import PathLike
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING, Any, TypeAlias
import contextlib
import logging

from niquests_cache.backends.base import BaseBackend
from niquests_cache.serializers import resolve_serializer
from typing_extensions import override
import anyio
import platformdirs

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from niquests_cache.typing import CacheEntry, Serializer

__all__ = ('FileCache', 'StrPath')

log = logging.getLogger(__name__)

StrPath: TypeAlias = str | PathLike[str]


class FileCache(BaseBackend):
    """Cache responses as serialised files in a directory."""
    def __init__(self,
                 cache_name: StrPath = 'http_cache',
                 *,
                 use_temp: bool = False,
                 use_cache_dir: bool = False,
                 extension: str = '',
                 lock: AbstractContextManager[Any] | None = None,
                 serializer: Serializer | str | None = None,
                 **kwargs: Any) -> None:  # noqa: ARG002
        path = Path(cache_name)
        if path.is_absolute():
            resolved = path
        elif use_cache_dir:
            resolved = platformdirs.user_cache_path() / path
        elif use_temp:
            resolved = Path(gettempdir()) / path
        else:
            resolved = path
        self._cache_dir = resolved
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._extension = extension
        self._lock: AbstractContextManager[Any] = (lock if lock is not None else nullcontext())
        self._serializer = resolve_serializer(serializer)

    @property
    def cache_dir(self) -> Path:
        """Filesystem directory holding cache files."""
        return self._cache_dir

    @property
    def serializer(self) -> Serializer:
        """The serialiser used to encode entries to bytes."""
        return self._serializer

    def _path(self, key: str) -> Path:
        return self._cache_dir / f'{key}{self._extension}'

    @override
    def get(self, key: str) -> CacheEntry | None:
        """
        Look up a cached entry.

        Parameters
        ----------
        key : str
            The cache key.

        Returns
        -------
        CacheEntry | None
            The stored entry, or ``None`` if the file is missing or unreadable.
        """
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with self._lock:
                payload = path.read_bytes()
        except OSError:  # pragma: no cover
            log.debug('Failed to read cache entry: %s', path, exc_info=True)
            return None
        try:
            return self._serializer.loads(payload)
        except (ValueError, KeyError):
            log.debug('Failed to decode cache entry: %s', path, exc_info=True)
            return None

    @override
    def set(self, key: str, entry: CacheEntry) -> None:
        """
        Persist a cache entry.

        Parameters
        ----------
        key : str
            The cache key.
        entry : CacheEntry
            The entry to store.
        """
        with contextlib.suppress(OSError), self._lock:  # pragma: no cover
            self._path(key).write_bytes(self._serializer.dumps(entry))

    @override
    async def aget(self, key: str) -> CacheEntry | None:
        """
        Async :meth:`get` using :mod:`anyio` for non-blocking I/O.

        Parameters
        ----------
        key : str
            The cache key.

        Returns
        -------
        CacheEntry | None
            The stored entry, or ``None`` if the file is missing or unreadable.
        """
        path = anyio.Path(self._path(key))
        if not await path.exists():
            return None
        try:
            payload = await path.read_bytes()
        except OSError:  # pragma: no cover
            log.debug('Failed to read cache entry: %s', path, exc_info=True)
            return None
        try:
            return self._serializer.loads(payload)
        except (ValueError, KeyError):
            log.debug('Failed to decode cache entry: %s', path, exc_info=True)
            return None

    @override
    async def aset(self, key: str, entry: CacheEntry) -> None:
        """
        Async :meth:`set` using :mod:`anyio` for non-blocking I/O.

        Parameters
        ----------
        key : str
            The cache key.
        entry : CacheEntry
            The entry to store.
        """
        path = anyio.Path(self._path(key))
        with contextlib.suppress(OSError):  # pragma: no cover
            await path.write_bytes(self._serializer.dumps(entry))
