"""In-memory cache backend."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from niquests_cache.backends.base import BaseBackend
from typing_extensions import override

if TYPE_CHECKING:
    from niquests_cache.typing import CacheEntry

__all__ = ('MemoryBackend',)


class MemoryBackend(BaseBackend):
    """Cache responses in an in-process dictionary."""
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}

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
            A shallow copy of the stored entry, or ``None`` if the key is unknown. The copy
            isolates callers from the backend's internal state so mutating the returned entry
            does not silently update the cache.
        """
        entry = self._store.get(key)
        return None if entry is None else cast('CacheEntry', dict(entry))

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
        self._store[key] = entry
