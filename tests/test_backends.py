"""Tests for :mod:`niquests_cache.backends`."""
from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir
from time import time
from typing import TYPE_CHECKING, Any

from niquests_cache.backends import FileCache, MemoryBackend, SQLiteBackend
from niquests_cache.serializers import PickleSerializer
import pytest

if TYPE_CHECKING:
    from niquests_cache.typing import CacheEntry
    from pytest_mock import MockerFixture


def _entry(content: bytes = b'hi',
           url: str = 'https://example.com/',
           ts_offset: float = 0,
           headers: dict[str, str] | None = None) -> CacheEntry:
    return {
        'content': content,
        'encoding': 'utf-8',
        'headers': dict({'X-Test': 'y'} if headers is None else headers),
        'status_code': 200,
        'ts': time() + ts_offset,
        'url': url
    }


def test_memory_backend_set_get() -> None:
    backend = MemoryBackend()
    backend.set('k', _entry(b'mem'))
    fetched = backend.get('k')
    assert fetched is not None
    assert fetched['content'] == b'mem'


def test_memory_backend_miss() -> None:
    assert MemoryBackend().get('missing') is None


def test_file_backend_set_get(tmp_path: Path) -> None:
    backend = FileCache(tmp_path / 'fb')
    backend.set('abc', _entry(b'disk'))
    fetched = backend.get('abc')
    assert fetched is not None
    assert fetched['content'] == b'disk'


def test_file_backend_miss(tmp_path: Path) -> None:
    assert FileCache(tmp_path).get('absent') is None


def test_file_backend_corrupted(tmp_path: Path) -> None:
    backend = FileCache(tmp_path)
    (tmp_path / 'bad').write_bytes(b'not json')
    assert backend.get('bad') is None


def test_file_backend_cache_dir(tmp_path: Path) -> None:
    backend = FileCache(tmp_path / 'cd')
    assert backend.cache_dir == tmp_path / 'cd'


def test_file_cache_serializer_default_is_json(tmp_path: Path) -> None:
    backend = FileCache(tmp_path)
    from niquests_cache.serializers import JSONSerializer
    assert isinstance(backend.serializer, JSONSerializer)


def test_file_cache_serializer_pickle_roundtrip(tmp_path: Path) -> None:
    backend = FileCache(tmp_path, serializer='pickle')
    entry = _entry(b'\x00\x01\x02binary')
    backend.set('k', entry)
    fetched = backend.get('k')
    assert fetched is not None
    assert fetched['content'] == b'\x00\x01\x02binary'


def test_file_cache_default_relative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    backend = FileCache()
    assert backend.cache_dir == Path('http_cache')
    assert (tmp_path / 'http_cache').is_dir()


def test_file_cache_use_temp() -> None:
    backend = FileCache('niquests_cache_temp_test', use_temp=True)
    assert backend.cache_dir == Path(gettempdir()) / 'niquests_cache_temp_test'
    assert backend.cache_dir.is_dir()


def test_file_cache_use_cache_dir(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch('niquests_cache.backends.file.platformdirs.user_cache_path',
                 return_value=tmp_path / 'user-cache')
    backend = FileCache('myapp', use_cache_dir=True)
    assert backend.cache_dir == tmp_path / 'user-cache' / 'myapp'


def test_file_cache_absolute_path_overrides_flags(tmp_path: Path) -> None:
    abs_path = tmp_path / 'abs'
    backend = FileCache(abs_path, use_temp=True, use_cache_dir=True)
    assert backend.cache_dir == abs_path


def test_file_cache_extension(tmp_path: Path) -> None:
    backend = FileCache(tmp_path, extension='.bin')
    backend.set('k', _entry(b'ext'))
    assert (tmp_path / 'k.bin').exists()
    fetched = backend.get('k')
    assert fetched is not None
    assert fetched['content'] == b'ext'


def test_file_cache_lock_used_on_get_and_set(tmp_path: Path, mocker: MockerFixture) -> None:
    lock = mocker.MagicMock()
    lock.__enter__ = mocker.MagicMock(return_value=None)
    lock.__exit__ = mocker.MagicMock(return_value=False)
    backend = FileCache(tmp_path, lock=lock)
    backend.set('k', _entry(b'locked'))
    backend.get('k')
    assert lock.__enter__.call_count >= 2


def test_file_cache_accepts_kwargs(tmp_path: Path) -> None:
    backend = FileCache(tmp_path, decode_content=True, max_cache_bytes=1024)
    assert backend.cache_dir == tmp_path


def test_sqlite_backend_set_get() -> None:
    backend = SQLiteBackend(':memory:')
    backend.set('k', _entry(b'sql'))
    fetched = backend.get('k')
    assert fetched is not None
    assert fetched['content'] == b'sql'


def test_sqlite_backend_columns(tmp_path: Path) -> None:
    db = tmp_path / 'cache.db'
    backend = SQLiteBackend(db)
    backend.set('k', _entry(b'binary\x00data', headers={'X-Foo': 'bar'}))
    import sqlite3
    conn = sqlite3.connect(db)
    row = conn.execute(
        'SELECT key, content, encoding, headers, status_code, ts, url '
        'FROM niquests_cache WHERE key = ?', ('k',)).fetchone()
    conn.close()
    assert row[0] == 'k'
    assert row[1] == b'binary\x00data'
    assert row[2] == 'utf-8'
    import json
    assert json.loads(row[3]) == {'X-Foo': 'bar'}
    assert row[4] == 200
    assert isinstance(row[5], float)
    assert row[6] == 'https://example.com/'


def test_sqlite_backend_binary_content_roundtrip() -> None:
    backend = SQLiteBackend(':memory:')
    raw = b'\x00\x01\x02\xff\xfe'
    backend.set('k', _entry(raw))
    fetched = backend.get('k')
    assert fetched is not None
    assert fetched['content'] == raw


def test_sqlite_backend_miss() -> None:
    assert SQLiteBackend(':memory:').get('absent') is None


def test_sqlite_backend_replace() -> None:
    backend = SQLiteBackend(':memory:')
    backend.set('k', _entry(b'first'))
    backend.set('k', _entry(b'second'))
    fetched = backend.get('k')
    assert fetched is not None
    assert fetched['content'] == b'second'


def test_sqlite_backend_invalid_table_name() -> None:
    with pytest.raises(ValueError, match='Invalid table name'):
        SQLiteBackend(':memory:', table_name='bad name; DROP TABLE x')


def test_sqlite_backend_persistent_path(tmp_path: Path) -> None:
    db = tmp_path / 'cache.db'
    backend = SQLiteBackend(db)
    backend.set('k', _entry(b'persisted'))
    fetched = SQLiteBackend(db).get('k')
    assert fetched is not None
    assert fetched['content'] == b'persisted'


def test_sqlite_backend_database_property(tmp_path: Path) -> None:
    db = tmp_path / 'd.db'
    backend = SQLiteBackend(db)
    assert backend.database == db


def test_sqlite_backend_close(tmp_path: Path) -> None:
    backend = SQLiteBackend(tmp_path / 'c.db')
    backend.close()
    with pytest.raises(Exception, match='Cannot operate on a closed database'):
        backend.get('k')


async def test_sqlite_backend_aset_aget(tmp_path: Path) -> None:
    backend = SQLiteBackend(tmp_path / 'a.db')
    await backend.aset('k', _entry(b'async-sql'))
    fetched = await backend.aget('k')
    assert fetched is not None
    assert fetched['content'] == b'async-sql'


async def test_sqlite_backend_aget_miss(tmp_path: Path) -> None:
    backend = SQLiteBackend(tmp_path / 'b.db')
    assert await backend.aget('missing') is None


async def test_file_cache_aset_aget(tmp_path: Path) -> None:
    backend = FileCache(tmp_path / 'fb-async')
    await backend.aset('k', _entry(b'async-disk'))
    fetched = await backend.aget('k')
    assert fetched is not None
    assert fetched['content'] == b'async-disk'


async def test_file_cache_aget_missing(tmp_path: Path) -> None:
    assert await FileCache(tmp_path).aget('absent') is None


async def test_file_cache_aget_corrupted(tmp_path: Path) -> None:
    backend = FileCache(tmp_path)
    (tmp_path / 'bad').write_bytes(b'not json')
    assert await backend.aget('bad') is None


async def test_memory_backend_async_default_methods() -> None:
    backend = MemoryBackend()
    await backend.aset('k', _entry(b'm'))
    fetched = await backend.aget('k')
    assert fetched is not None
    assert fetched['content'] == b'm'


def test_pickle_serializer_roundtrip() -> None:
    ser = PickleSerializer()
    entry = _entry(b'\x00\x01raw')
    payload = ser.dumps(entry)
    decoded = ser.loads(payload)
    assert decoded['content'] == b'\x00\x01raw'


def test_pickle_serializer_loads_callable() -> None:
    ser = PickleSerializer()
    payload = ser.dumps(_entry(b'p'))
    out: Any = ser.loads(payload)
    assert out['content'] == b'p'
