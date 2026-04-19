"""Abstract base class for cache backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from niquests_cache.typing import CacheEntry

__all__ = ('BaseBackend',)


class BaseBackend(ABC):
    """Abstract storage backend used by :class:`~niquests_cache.CachedSession`."""
    @abstractmethod
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
            The stored entry, or ``None`` if the key is unknown.
        """

    @abstractmethod
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

    async def aget(self, key: str) -> CacheEntry | None:
        """
        Async :meth:`get`. Default implementation calls the sync version.

        Parameters
        ----------
        key : str
            The cache key.

        Returns
        -------
        CacheEntry | None
            The stored entry, or ``None`` if the key is unknown.
        """
        return self.get(key)

    async def aset(self, key: str, entry: CacheEntry) -> None:
        """
        Async :meth:`set`. Default implementation calls the sync version.

        Parameters
        ----------
        key : str
            The cache key.
        entry : CacheEntry
            The entry to store.
        """
        self.set(key, entry)
