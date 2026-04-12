"""Filesystem-cached :mod:`niquests` sessions."""
from __future__ import annotations

from niquests_cache.session import CachedAsyncSession, CachedSession, cached_session

__all__ = ('CachedAsyncSession', 'CachedSession', 'cached_session')
__version__ = '0.0.1'
