"""Typing helpers for :mod:`niquests_cache`."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol, TypeAlias, TypedDict, runtime_checkable

__all__ = ('CacheEntry', 'ExpireAfter', 'Serializer')

ExpireAfter: TypeAlias = int | float | str | datetime | timedelta | None
"""Accepted types for the ``expire_after`` parameter."""


class CacheEntry(TypedDict):
    """A cached HTTP response entry."""

    content: bytes
    """Response body as raw bytes."""
    encoding: str
    """Response encoding."""
    headers: dict[str, str]
    """Response headers."""
    status_code: int
    """HTTP status code."""
    ts: float
    """Unix timestamp the entry was written."""
    url: str
    """Final response URL."""


@runtime_checkable
class Serializer(Protocol):
    """Structural type for serialiser objects with ``dumps``/``loads`` methods."""
    def dumps(self, entry: CacheEntry) -> bytes:
        """
        Serialise a :class:`CacheEntry` to bytes.

        Parameters
        ----------
        entry : CacheEntry
            The cache entry to serialise.

        Returns
        -------
        bytes
            The serialised payload.
        """

    def loads(self, data: bytes) -> CacheEntry:
        """
        Deserialise bytes back into a :class:`CacheEntry`.

        Parameters
        ----------
        data : bytes
            The serialised payload.

        Returns
        -------
        CacheEntry
            The decoded cache entry.
        """
