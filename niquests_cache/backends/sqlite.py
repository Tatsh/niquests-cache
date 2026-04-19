"""SQLite cache backend storing entries in typed columns."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
import json
import re
import sqlite3
import weakref

from niquests_cache.backends.base import BaseBackend
from typing_extensions import override
import aiosqlite

if TYPE_CHECKING:
    from niquests_cache.backends.file import StrPath
    from niquests_cache.typing import CacheEntry

__all__ = ('SQLiteBackend',)

_TABLE_PATTERN = '^[A-Za-z_][A-Za-z0-9_]*$'
_SCHEMA = ('CREATE TABLE IF NOT EXISTS {table} ('
           'key TEXT PRIMARY KEY, '
           'content BLOB NOT NULL, '
           'encoding TEXT NOT NULL, '
           'headers TEXT NOT NULL, '
           'status_code INTEGER NOT NULL, '
           'ts REAL NOT NULL, '
           'url TEXT NOT NULL'
           ')')


def _validate_table(name: str) -> str:
    if not re.match(_TABLE_PATTERN, name):
        msg = f'Invalid table name: {name!r}.'
        raise ValueError(msg)
    return name


def _row_to_entry(row: tuple[Any, ...]) -> CacheEntry:
    content, encoding, headers_json, status_code, ts, url = row
    return {
        'content': bytes(content),
        'encoding': encoding,
        'headers': cast('dict[str, str]', json.loads(headers_json)),
        'status_code': status_code,
        'ts': ts,
        'url': url,
    }


def _entry_row(key: str, entry: CacheEntry) -> tuple[Any, ...]:
    return (key, entry['content'], entry['encoding'], json.dumps(dict(
        entry['headers'])), entry['status_code'], entry['ts'], entry['url'])


class SQLiteBackend(BaseBackend):
    """Cache responses in a SQLite database with typed columns."""

    _SELECT = ('SELECT content, encoding, headers, status_code, ts, url '
               'FROM {table} WHERE key = ?')
    _UPSERT = ('INSERT OR REPLACE INTO {table} '
               '(key, content, encoding, headers, status_code, ts, url) '
               'VALUES (?, ?, ?, ?, ?, ?, ?)')

    def __init__(self,
                 database: StrPath = ':memory:',
                 *,
                 table_name: str = 'niquests_cache') -> None:
        self._database = database
        self._table = _validate_table(table_name)
        if database != ':memory:':
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(database)
        self._conn.execute(_SCHEMA.format(table=self._table))
        self._conn.commit()
        self._finalizer = weakref.finalize(self, self._conn.close)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._finalizer()

    @property
    def database(self) -> StrPath:
        """SQLite database path (or ``':memory:'``)."""
        return self._database

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
            The stored entry, or ``None`` if not present.
        """
        row = self._conn.execute(self._SELECT.format(table=self._table), (key,)).fetchone()
        return None if row is None else _row_to_entry(row)

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
        self._conn.execute(self._UPSERT.format(table=self._table), _entry_row(key, entry))
        self._conn.commit()

    @override
    async def aget(self, key: str) -> CacheEntry | None:
        """
        Async :meth:`get` using :mod:`aiosqlite`.

        Parameters
        ----------
        key : str
            The cache key.

        Returns
        -------
        CacheEntry | None
            The stored entry, or ``None`` if not present.
        """
        async with aiosqlite.connect(str(self._database)) as db, db.execute(
                self._SELECT.format(table=self._table), (key,)) as cur:
            row = await cur.fetchone()
        return None if row is None else _row_to_entry(tuple(row))

    @override
    async def aset(self, key: str, entry: CacheEntry) -> None:
        """
        Async :meth:`set` using :mod:`aiosqlite`.

        Parameters
        ----------
        key : str
            The cache key.
        entry : CacheEntry
            The entry to store.
        """
        async with aiosqlite.connect(str(self._database)) as db:
            await db.execute(self._UPSERT.format(table=self._table), _entry_row(key, entry))
            await db.commit()
