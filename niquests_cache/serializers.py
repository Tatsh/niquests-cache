"""Built-in serialisers for cache entries."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast
import base64
import json
import pickle  # noqa: S403

if TYPE_CHECKING:
    from niquests_cache.typing import CacheEntry, Serializer

__all__ = ('JsonSerializer', 'PickleSerializer', 'resolve_serializer')


class JsonSerializer:
    """Encodes :class:`CacheEntry` as UTF-8 JSON. Binary ``content`` is base64-encoded."""
    def dumps(self, entry: CacheEntry) -> bytes:  # noqa: PLR6301
        """
        Serialise ``entry`` to JSON-encoded bytes.

        Parameters
        ----------
        entry : CacheEntry
            The cache entry to serialise.

        Returns
        -------
        bytes
            The encoded payload.
        """
        copy = dict(entry)
        copy['content'] = base64.b64encode(entry['content']).decode()
        return json.dumps(copy).encode()

    def loads(self, data: bytes) -> CacheEntry:  # noqa: PLR6301
        """
        Deserialise a JSON-encoded payload.

        Parameters
        ----------
        data : bytes
            The serialised payload.

        Returns
        -------
        CacheEntry
            The decoded cache entry.
        """
        decoded = json.loads(data)
        decoded['content'] = base64.b64decode(decoded['content'])
        return cast('CacheEntry', decoded)


class PickleSerializer:
    """Encodes :class:`CacheEntry` using :mod:`pickle`."""
    def dumps(self, entry: CacheEntry) -> bytes:  # noqa: PLR6301
        """
        Serialise ``entry`` using :func:`pickle.dumps`.

        Parameters
        ----------
        entry : CacheEntry
            The cache entry to serialise.

        Returns
        -------
        bytes
            The pickled payload.
        """
        return pickle.dumps(dict(entry))

    def loads(self, data: bytes) -> CacheEntry:  # noqa: PLR6301
        """
        Deserialise a pickled payload.

        Parameters
        ----------
        data : bytes
            The serialised payload.

        Returns
        -------
        CacheEntry
            The decoded cache entry.
        """
        return cast('CacheEntry', pickle.loads(data))  # noqa: S301


def resolve_serializer(value: str | Serializer | None) -> Serializer:
    """
    Resolve a ``serializer`` argument.

    Parameters
    ----------
    value : str | Serializer | None
        Built-in alias (``'json'`` or ``'pickle'``), an object exposing ``dumps``/``loads``, or
        ``None`` for the default JSON serialiser.

    Returns
    -------
    Serializer
        The resolved serialiser.

    Raises
    ------
    TypeError
        If ``value`` is an unknown alias or lacks ``dumps``/``loads`` methods.
    """
    if value is None or value == 'json':
        return JsonSerializer()
    if value == 'pickle':
        return PickleSerializer()
    if isinstance(value, str):
        msg = f'Unknown serializer: {value!r}.'
        raise TypeError(msg)
    missing = [name for name in ('dumps', 'loads') if not hasattr(value, name)]
    if missing:
        msg = f'Custom serializer is missing required method(s): {", ".join(missing)}.'
        raise TypeError(msg)
    return value
