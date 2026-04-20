"""Cached :mod:`niquests` sessions with pluggable storage backends."""
from __future__ import annotations

from niquests_cache.session import AsyncCachedSession, CachedSession, cached_session

__all__ = ('AsyncCachedSession', 'CachedSession', 'cached_session')
__version__ = '0.2.1'
