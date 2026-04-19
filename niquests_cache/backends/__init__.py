"""Cache backends for :mod:`niquests_cache`."""
from __future__ import annotations

from niquests_cache.backends.base import BaseBackend
from niquests_cache.backends.file import FileCache
from niquests_cache.backends.memory import MemoryBackend
from niquests_cache.backends.sqlite import SQLiteBackend

__all__ = ('BaseBackend', 'FileCache', 'MemoryBackend', 'SQLiteBackend')
