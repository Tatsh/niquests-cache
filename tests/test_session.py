"""Tests for :mod:`niquests_cache.session`."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from time import time
from typing import TYPE_CHECKING, Any, cast
import json
import re

from niquests_cache import AsyncCachedSession, CachedSession, cached_session
from niquests_cache.backends import FileCache, MemoryBackend, SQLiteBackend
from niquests_cache.serializers import JSONSerializer, PickleSerializer
import niquests
import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from niquests_cache.typing import CacheEntry
    from pytest_mock import MockerFixture


def _key(method: str, url: str, headers: Mapping[str, str] | None = None) -> str:
    hdr = ''
    if headers:
        hdr = json.dumps(sorted((k.lower(), str(v)) for k, v in headers.items()),
                         separators=(',', ':'))
    return sha256(f'{method} {url} {hdr}'.encode()).hexdigest()


def _session_headers(session: niquests.Session | niquests.AsyncSession,
                     extra: Mapping[str, str] | None = None) -> dict[str, str]:
    raw: dict[str, Any] = dict(session.headers)
    merged = {k: str(v) for k, v in raw.items() if v is not None}
    if extra:
        merged.update({k: str(v) for k, v in extra.items() if v is not None})
    return merged


def _mock_resp(content: bytes = b'body',
               url: str = 'https://example.com/x',
               status: int = 200) -> niquests.Response:
    resp = niquests.Response()
    resp.status_code = status
    resp._content = content  # noqa: SLF001
    resp.url = url
    resp.encoding = 'utf-8'
    return resp


def _entry(content: bytes = b'body',
           url: str = 'https://example.com/x',
           ts_offset: float = 0,
           headers: Mapping[str, str] | None = None) -> CacheEntry:
    return {
        'content': content,
        'encoding': 'utf-8',
        'headers': dict(headers or {}),
        'status_code': 200,
        'ts': time() + ts_offset,
        'url': url,
    }


@pytest.mark.usefixtures('mock_user_cache_path')
def test_cached_session_returns_cached_session() -> None:
    assert isinstance(cached_session(), CachedSession)


@pytest.mark.usefixtures('mock_user_cache_path')
def test_cached_session_aio_returns_async_cached_session() -> None:
    assert isinstance(cached_session(aio=True), AsyncCachedSession)


@pytest.mark.usefixtures('mock_user_cache_path')
def test_cached_session_helper_default_is_sqlite() -> None:
    session = cached_session()
    assert isinstance(session.cache, SQLiteBackend)


@pytest.mark.usefixtures('mock_user_cache_path')
def test_cached_session_helper_backend_alias() -> None:
    session = cached_session(backend='memory')
    assert isinstance(session.cache, MemoryBackend)


def test_cached_session_helper_backend_instance() -> None:
    backend = MemoryBackend()
    session = cached_session(backend=backend)
    assert session.cache is backend


def test_cached_session_uses_user_cache_path(tmp_path: Path, mocker: MockerFixture) -> None:
    fake_root = tmp_path / 'user-cache-root'
    fake_root.mkdir()
    mock_pd = mocker.patch('niquests_cache.session.platformdirs.user_cache_path',
                           return_value=fake_root)
    cached_session()
    mock_pd.assert_called_once_with('niquests-cache', appauthor=False, ensure_exists=True)
    assert (fake_root / 'http.sqlite').exists()


def test_cached_session_custom_app_name(tmp_path: Path, mocker: MockerFixture) -> None:
    fake_root = tmp_path / 'user-cache-root'
    fake_root.mkdir()
    mock_pd = mocker.patch('niquests_cache.session.platformdirs.user_cache_path',
                           return_value=fake_root)
    cached_session(app_name='my-tool')
    mock_pd.assert_called_once_with('my-tool', appauthor=False, ensure_exists=True)


def test_cached_session_no_cache_returns_plain_session() -> None:
    assert type(cached_session(no_cache=True)) is niquests.Session


def test_cached_session_no_cache_aio_returns_plain_async_session() -> None:
    assert type(cached_session(aio=True, no_cache=True)) is niquests.AsyncSession


def test_cached_session_default_backend_is_sqlite(tmp_path: Path) -> None:
    session = CachedSession(cache_name=tmp_path / 'cache')
    assert isinstance(session.cache, SQLiteBackend)


def test_cached_session_backend_alias_filesystem(tmp_path: Path) -> None:
    session = CachedSession(cache_name=tmp_path / 'fs', backend='filesystem')
    assert isinstance(session.cache, FileCache)


def test_cached_session_backend_alias_memory(tmp_path: Path) -> None:
    session = CachedSession(cache_name=tmp_path, backend='memory')
    assert isinstance(session.cache, MemoryBackend)


def test_cached_session_backend_alias_sqlite_memory() -> None:
    session = CachedSession(cache_name=':memory:', backend='sqlite')
    assert isinstance(session.cache, SQLiteBackend)


def test_cached_session_unknown_backend_alias() -> None:
    with pytest.raises(ValueError, match='Unknown backend alias'):
        CachedSession(backend=cast('Any', 'nope'))


def test_cached_session_backend_instance_used_directly() -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend)
    assert session.cache is backend
    assert session.backend is backend


def test_cached_session_serializer_default_is_json() -> None:
    session = CachedSession(backend=MemoryBackend())
    assert isinstance(session.settings.serializer, JSONSerializer)


def test_cached_session_serializer_alias_pickle() -> None:
    session = CachedSession(backend=MemoryBackend(), serializer='pickle')
    assert isinstance(session.settings.serializer, PickleSerializer)


def test_cached_session_serializer_unknown_string() -> None:
    with pytest.raises(TypeError, match='Unknown serializer'):
        CachedSession(backend=MemoryBackend(), serializer='yaml')


def test_cached_session_serializer_invalid_object() -> None:
    with pytest.raises(TypeError, match='dumps, loads'):
        CachedSession(backend=MemoryBackend(), serializer=cast('Any', object()))


def test_cached_session_serializer_partial_object() -> None:
    class HalfSer:
        def dumps(self, entry: Any) -> bytes:  # noqa: PLR6301
            del entry
            return b''

    with pytest.raises(TypeError, match='loads'):
        CachedSession(backend=MemoryBackend(), serializer=cast('Any', HalfSer()))


def test_cached_session_serializer_custom_object() -> None:
    class MySer:
        def dumps(self, entry: Any) -> bytes:  # noqa: PLR6301
            del entry
            return b'x'

        def loads(self, data: bytes) -> Any:  # noqa: PLR6301
            del data
            return _entry()

    ser = MySer()
    session = CachedSession(backend=MemoryBackend(), serializer=ser)
    assert session.settings.serializer is ser


def test_cached_session_filesystem_alias_uses_serializer(tmp_path: Path,
                                                         mocker: MockerFixture) -> None:
    session = CachedSession(cache_name=tmp_path / 'fs', backend='filesystem', serializer='pickle')
    backend = cast('FileCache', session.cache)
    assert isinstance(backend.serializer, PickleSerializer)
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'\x00\x01bin', 'https://example.com/b'))
    session.request('GET', 'https://example.com/b')
    fetched = backend.get(_key('GET', 'https://example.com/b'))
    assert fetched is not None
    assert fetched['content'] == b'\x00\x01bin'


def test_cached_session_cache_hit_with_match_headers(tmp_path: Path, mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, match_headers=True)
    backend.set(_key('GET', 'https://example.com/data', _session_headers(session)),
                _entry(b'cached body', 'https://example.com/data', headers={'X-Custom': 'val'}))
    parent = mocker.patch.object(niquests.Session, 'request', return_value=None)
    response = session.request('GET', 'https://example.com/data')
    parent.assert_not_called()
    assert response.content == b'cached body'


def test_cached_session_cache_hit_without_match_headers(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend)
    backend.set(_key('GET', 'https://example.com/data'),
                _entry(b'no-headers body', 'https://example.com/data'))
    parent = mocker.patch.object(niquests.Session, 'request', return_value=None)
    resp = session.request('GET', 'https://example.com/data')
    parent.assert_not_called()
    assert resp.content == b'no-headers body'


def test_cached_session_cache_expired(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, expire_after=timedelta(seconds=1))
    backend.set(_key('GET', 'https://example.com/old'),
                _entry(b'stale', 'https://example.com/old', ts_offset=-100))
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'fresh', 'https://example.com/old'))
    resp = session.request('GET', 'https://example.com/old')
    assert resp.content == b'fresh'


def test_cached_session_force_refresh(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend)
    backend.set(_key('GET', 'https://example.com/x'), _entry(b'cached'))
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'fresh'))
    resp = session.request('GET', 'https://example.com/x', force_refresh=True)
    assert resp.content == b'fresh'


def test_cached_session_refresh_kwarg_bypasses_read(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend)
    backend.set(_key('GET', 'https://example.com/x'), _entry(b'cached'))
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'fresh'))
    resp = session.request('GET', 'https://example.com/x', refresh=True)
    assert resp.content == b'fresh'


def test_cached_session_only_if_cached_miss_returns_504(mocker: MockerFixture) -> None:
    session = CachedSession(backend=MemoryBackend())
    parent = mocker.patch.object(niquests.Session, 'request')
    resp = session.request('GET', 'https://example.com/missing', only_if_cached=True)
    assert resp.status_code == 504
    parent.assert_not_called()


def test_cached_session_only_if_cached_hit(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/x'), _entry(b'hit'))
    session = CachedSession(backend=backend)
    parent = mocker.patch.object(niquests.Session, 'request')
    resp = session.request('GET', 'https://example.com/x', only_if_cached=True)
    assert resp.content == b'hit'
    parent.assert_not_called()


def test_cached_session_post_not_cached(mocker: MockerFixture) -> None:
    session = CachedSession(backend=MemoryBackend())
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'created',
                                                         'https://example.com/api',
                                                         status=201))
    resp = session.request('POST', 'https://example.com/api')
    parent.assert_called_once()
    assert resp.status_code == 201
    assert session.cache.get(_key('POST', 'https://example.com/api')) is None


def test_cached_session_allowable_methods_includes_post(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, allowable_methods=('GET', 'HEAD', 'POST'))
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'ok', 'https://example.com/api'))
    session.request('POST', 'https://example.com/api')
    assert backend.get(_key('POST', 'https://example.com/api')) is not None


def test_cached_session_allowable_codes_excludes_404(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend)
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'gone', 'https://example.com/g', status=404))
    session.request('GET', 'https://example.com/g')
    assert backend.get(_key('GET', 'https://example.com/g')) is None


def test_cached_session_allowable_codes_includes_404(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, allowable_codes=(200, 404))
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'gone', 'https://example.com/g', status=404))
    session.request('GET', 'https://example.com/g')
    assert backend.get(_key('GET', 'https://example.com/g')) is not None


def test_cached_session_filter_fn_rejects_response(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, filter_fn=lambda _: False)
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'ok'))
    session.request('GET', 'https://example.com/x')
    assert backend.get(_key('GET', 'https://example.com/x')) is None


def test_cached_session_read_only_skips_writes(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, read_only=True)
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'ok'))
    session.request('GET', 'https://example.com/x')
    assert backend.get(_key('GET', 'https://example.com/x')) is None


def test_cached_session_ignored_parameters_strip_from_url(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, ignored_parameters=('access_token',))
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'ok'))
    session.request('GET', 'https://example.com/x?access_token=abc&id=1')
    stripped = 'https://example.com/x?id=1'
    assert backend.get(_key('GET', stripped)) is not None


def test_cached_session_match_headers_iterable(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend, match_headers=('Accept',))
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'a'))
    session.request('GET', 'https://example.com/v', headers={'Accept': 'application/json'})
    expected = _key('GET', 'https://example.com/v', {'Accept': 'application/json'})
    assert backend.get(expected) is not None


def test_cached_session_key_fn_used(mocker: MockerFixture) -> None:
    backend = MemoryBackend()

    def my_key(*, method: str, url: str, headers: Any) -> str:
        del headers
        return f'custom::{method}::{url}'

    session = CachedSession(backend=backend, key_fn=my_key)
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'k'))
    session.request('GET', 'https://example.com/x')
    assert backend.get('custom::GET::https://example.com/x') is not None


def test_cached_session_urls_expire_after_glob(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/short/x'),
                _entry(b'old', 'https://example.com/short/x', ts_offset=-1))
    session = CachedSession(backend=backend,
                            expire_after=-1,
                            urls_expire_after={'*example.com/short*': 0.001})
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'fresh', 'https://example.com/short/x'))
    resp = session.request('GET', 'https://example.com/short/x')
    parent.assert_called_once()
    assert resp.content == b'fresh'


def test_cached_session_urls_expire_after_no_match(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/u'),
                _entry(b'fallback-ttl', 'https://example.com/u'))
    session = CachedSession(backend=backend, expire_after=-1, urls_expire_after={'*nope*': 1})
    parent = mocker.patch.object(niquests.Session, 'request')
    resp = session.request('GET', 'https://example.com/u')
    parent.assert_not_called()
    assert resp.content == b'fallback-ttl'


def test_cached_session_urls_expire_after_multiple_patterns(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/y/x'),
                _entry(b'old', 'https://example.com/y/x', ts_offset=-100))
    session = CachedSession(backend=backend,
                            expire_after=-1,
                            urls_expire_after={
                                '*x/never*': -1,
                                '*y/x*': 1
                            })
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'fresh', 'https://example.com/y/x'))
    resp = session.request('GET', 'https://example.com/y/x')
    assert resp.content == b'fresh'


def test_cached_session_urls_expire_after_pattern() -> None:
    pattern = re.compile(r'/never/')
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/never/x'),
                _entry(b'kept', 'https://example.com/never/x', ts_offset=-100))
    session = CachedSession(backend=backend, expire_after=0, urls_expire_after={pattern: -1})
    resp = session.request('GET', 'https://example.com/never/x')
    assert resp.content == b'kept'


def test_cached_session_expire_after_seconds(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/s'),
                _entry(b'old', 'https://example.com/s', ts_offset=-5))
    session = CachedSession(backend=backend, expire_after=1)
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'fresh', 'https://example.com/s'))
    resp = session.request('GET', 'https://example.com/s')
    assert resp.content == b'fresh'


def test_cached_session_expire_after_datetime() -> None:
    future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    session = CachedSession(backend=MemoryBackend(), expire_after=future)
    assert session.settings.expire_after == future


def test_cached_session_expire_after_invalid_type() -> None:
    session = CachedSession(backend=MemoryBackend(), expire_after=cast('Any', object()))
    with pytest.raises(TypeError, match='Unsupported expire_after type'):
        session.request('GET', 'https://example.com/x')


def test_cached_session_expire_after_bool_rejected() -> None:
    session = CachedSession(backend=MemoryBackend(), expire_after=True)
    with pytest.raises(TypeError, match='may not be a bool'):
        session.request('GET', 'https://example.com/x')


def test_cached_session_per_request_expire_after(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/p'),
                _entry(b'old', 'https://example.com/p', ts_offset=-5))
    session = CachedSession(backend=backend, expire_after=timedelta(hours=1))
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'fresh', 'https://example.com/p'))
    resp = session.request('GET', 'https://example.com/p', expire_after=1)
    assert resp.content == b'fresh'


def test_cached_session_cache_disabled(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend)
    mocker.patch.object(niquests.Session, 'request', return_value=_mock_resp(b'live'))
    with session.cache_disabled():
        session.request('GET', 'https://example.com/d')
    assert backend.get(_key('GET', 'https://example.com/d')) is None


def test_cached_session_settings_mutable() -> None:
    session = CachedSession(backend=MemoryBackend())
    session.settings.expire_after = 60
    assert session.settings.expire_after == 60


def test_cached_session_corrupted_cache_falls_back(tmp_path: Path, mocker: MockerFixture) -> None:
    session = CachedSession(backend=FileCache(tmp_path))
    (tmp_path / _key('GET', 'https://example.com/bad')).write_bytes(b'not json')
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'real', 'https://example.com/bad'))
    resp = session.request('GET', 'https://example.com/bad')
    assert resp.content == b'real'


def test_cached_session_malformed_entry_falls_back(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/m'), cast('CacheEntry', {'ts': time()}))
    session = CachedSession(backend=backend)
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'good', 'https://example.com/m'))
    resp = session.request('GET', 'https://example.com/m')
    assert resp.content == b'good'


def test_cached_session_head_request_cached(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = CachedSession(backend=backend)
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'', 'https://example.com/head'))
    session.request('HEAD', 'https://example.com/head')
    assert backend.get(_key('HEAD', 'https://example.com/head')) is not None


def test_cached_session_header_differentiation(mocker: MockerFixture) -> None:
    session = CachedSession(backend=MemoryBackend(), match_headers=True)
    json_resp = _mock_resp(b'{"k": 1}', 'https://example.com/v')
    xml_resp = _mock_resp(b'<k>1</k>', 'https://example.com/v')
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 side_effect=[json_resp, xml_resp, json_resp, xml_resp])
    r1 = session.request('GET', 'https://example.com/v', headers={'Accept': 'application/json'})
    r2 = session.request('GET', 'https://example.com/v', headers={'Accept': 'application/xml'})
    r3 = session.request('GET', 'https://example.com/v', headers={'Accept': 'application/json'})
    r4 = session.request('GET', 'https://example.com/v', headers={'Accept': 'application/xml'})
    assert r1.content == b'{"k": 1}'
    assert r2.content == b'<k>1</k>'
    assert r3.content == b'{"k": 1}'
    assert r4.content == b'<k>1</k>'
    assert parent.call_count == 2


def test_cached_session_header_removal_via_none(mocker: MockerFixture) -> None:
    session = CachedSession(backend=MemoryBackend(), match_headers=True)
    session.headers.clear()
    session.headers['X-Token'] = 'abc'
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'x', 'https://example.com/rm'))
    session.request('GET', 'https://example.com/rm', headers=cast('Any', {'X-Token': None}))
    assert session.cache.get(_key('GET', 'https://example.com/rm')) is not None


def test_cached_session_empty_headers_cache_key(mocker: MockerFixture) -> None:
    session = CachedSession(backend=MemoryBackend(), match_headers=True)
    session.headers.clear()
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'x', 'https://example.com/empty'))
    session.request('GET', 'https://example.com/empty')
    assert session.cache.get(_key('GET', 'https://example.com/empty')) is not None


def test_cached_session_expire_after_none_means_never(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/n'),
                _entry(b'ancient', 'https://example.com/n', ts_offset=-10_000))
    session = CachedSession(backend=backend, expire_after=None)
    parent = mocker.patch.object(niquests.Session, 'request')
    resp = session.request('GET', 'https://example.com/n')
    parent.assert_not_called()
    assert resp.content == b'ancient'


def test_cached_session_request_with_datetime_expire(mocker: MockerFixture) -> None:
    future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/dt'), _entry(b'in-window',
                                                              'https://example.com/dt'))
    session = CachedSession(backend=backend, expire_after=future)
    parent = mocker.patch.object(niquests.Session, 'request')
    resp = session.request('GET', 'https://example.com/dt')
    parent.assert_not_called()
    assert resp.content == b'in-window'


async def test_async_cached_session_basic_hit(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/a'), _entry(b'cached', 'https://example.com/a'))
    session = AsyncCachedSession(backend=backend)
    parent = mocker.patch.object(niquests.AsyncSession, 'request', return_value=None)
    resp = await session.request('GET', 'https://example.com/a')
    assert resp.content == b'cached'
    parent.assert_not_called()


async def test_async_cached_session_miss_stores(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = AsyncCachedSession(backend=backend)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'new', 'https://example.com/a'))
    await session.request('GET', 'https://example.com/a')
    assert backend.get(_key('GET', 'https://example.com/a')) is not None


async def test_async_cached_session_force_refresh(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/a'), _entry(b'old', 'https://example.com/a'))
    session = AsyncCachedSession(backend=backend)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'new', 'https://example.com/a'))
    resp = await session.request('GET', 'https://example.com/a', force_refresh=True)
    assert resp.content == b'new'


async def test_async_cached_session_only_if_cached_miss(mocker: MockerFixture) -> None:
    session = AsyncCachedSession(backend=MemoryBackend())
    parent = mocker.patch.object(niquests.AsyncSession, 'request')
    resp = await session.request('GET', 'https://example.com/x', only_if_cached=True)
    assert resp.status_code == 504
    parent.assert_not_called()


async def test_async_cached_session_post_not_cached(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = AsyncCachedSession(backend=backend)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'created', 'https://example.com/api', status=201))
    await session.request('POST', 'https://example.com/api')
    assert backend.get(_key('POST', 'https://example.com/api')) is None


async def test_async_cached_session_cache_disabled(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = AsyncCachedSession(backend=backend)
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=_mock_resp(b'live'))
    async with session.cache_disabled():
        await session.request('GET', 'https://example.com/d')
    assert backend.get(_key('GET', 'https://example.com/d')) is None


async def test_async_cached_session_404_not_stored(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = AsyncCachedSession(backend=backend)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'gone', 'https://example.com/g', status=404))
    await session.request('GET', 'https://example.com/g')
    assert backend.get(_key('GET', 'https://example.com/g')) is None


async def test_async_cached_session_method_not_in_allowable(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    session = AsyncCachedSession(backend=backend, allowable_methods=('GET',))
    parent = mocker.patch.object(niquests.AsyncSession, 'request', return_value=_mock_resp(b'x'))
    await session.request('HEAD', 'https://example.com/x')
    parent.assert_called_once()
    assert backend.get(_key('HEAD', 'https://example.com/x')) is None


async def test_async_cached_session_with_sqlite_backend(tmp_path: Path,
                                                        mocker: MockerFixture) -> None:
    session = AsyncCachedSession(cache_name=tmp_path / 'cache', backend='sqlite')
    assert isinstance(session.cache, SQLiteBackend)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'hi', 'https://example.com/sql'))
    await session.request('GET', 'https://example.com/sql')
    assert await session.cache.aget(_key('GET', 'https://example.com/sql')) is not None


async def test_async_cached_session_with_file_cache(tmp_path: Path, mocker: MockerFixture) -> None:
    session = AsyncCachedSession(cache_name=tmp_path / 'fs', backend='filesystem')
    assert isinstance(session.cache, FileCache)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'fs', 'https://example.com/fs'))
    await session.request('GET', 'https://example.com/fs')
    assert await session.cache.aget(_key('GET', 'https://example.com/fs')) is not None


async def test_async_cached_session_headers_param(mocker: MockerFixture) -> None:
    session = AsyncCachedSession(backend=MemoryBackend(), match_headers=('Accept',))
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'h', 'https://example.com/h'))
    await session.request('GET', 'https://example.com/h', headers={'Accept': 'application/json'})
    expected = _key('GET', 'https://example.com/h', {'Accept': 'application/json'})
    assert session.cache.get(expected) is not None


async def test_async_cached_session_expired(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/e'),
                _entry(b'old', 'https://example.com/e', ts_offset=-100))
    session = AsyncCachedSession(backend=backend, expire_after=1)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'fresh', 'https://example.com/e'))
    resp = await session.request('GET', 'https://example.com/e')
    assert resp.content == b'fresh'


async def test_async_cached_session_malformed_entry(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    backend.set(_key('GET', 'https://example.com/m'), cast('CacheEntry', {'ts': time()}))
    session = AsyncCachedSession(backend=backend)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'good', 'https://example.com/m'))
    resp = await session.request('GET', 'https://example.com/m')
    assert resp.content == b'good'


def test_cached_session_304_not_modified_refreshes_entry(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'original', 'https://example.com/cond', headers={'ETag': '"v1"'})
    key = _key('GET', 'https://example.com/cond')
    backend.set(key, entry)
    session = CachedSession(backend=backend, cache_control=True, always_revalidate=True)
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'', 'https://example.com/cond', status=304))
    resp = session.request('GET', 'https://example.com/cond')
    assert resp.content == b'original'
    refreshed = backend.get(key)
    assert refreshed is not None
    assert refreshed['ts'] >= entry['ts']


def test_cached_session_cache_control_attaches_validators(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'cached',
                   'https://example.com/val',
                   headers={
                       'ETag': '"e1"',
                       'Last-Modified': 'Mon, 01 Jan 2024 00:00:00 GMT'
                   })
    key = _key('GET', 'https://example.com/val')
    backend.set(key, entry)
    session = CachedSession(backend=backend, cache_control=True, always_revalidate=True)
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'new', 'https://example.com/val'))
    session.request('GET', 'https://example.com/val')
    call_kwargs = parent.call_args[1]
    assert call_kwargs['headers']['If-None-Match'] == '"e1"'
    assert call_kwargs['headers']['If-Modified-Since'] == 'Mon, 01 Jan 2024 00:00:00 GMT'


def test_cached_session_cache_control_no_validators(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'cached', 'https://example.com/noval', headers={'Content-Type': 'text/html'})
    key = _key('GET', 'https://example.com/noval')
    backend.set(key, entry)
    session = CachedSession(backend=backend, cache_control=True, always_revalidate=True)
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'new', 'https://example.com/noval'))
    session.request('GET', 'https://example.com/noval')
    call_kwargs = parent.call_args[1]
    assert 'If-None-Match' not in call_kwargs.get('headers', {})
    assert 'If-Modified-Since' not in call_kwargs.get('headers', {})


def test_cached_session_cache_control_last_modified_only(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'cached',
                   'https://example.com/lm',
                   headers={'Last-Modified': 'Mon, 01 Jan 2024 00:00:00 GMT'})
    key = _key('GET', 'https://example.com/lm')
    backend.set(key, entry)
    session = CachedSession(backend=backend, cache_control=True, always_revalidate=True)
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'new', 'https://example.com/lm'))
    session.request('GET', 'https://example.com/lm')
    call_kwargs = parent.call_args[1]
    assert 'If-None-Match' not in call_kwargs.get('headers', {})
    assert call_kwargs['headers']['If-Modified-Since'] == 'Mon, 01 Jan 2024 00:00:00 GMT'


async def test_async_cached_session_304_not_modified(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'original', 'https://example.com/acond', headers={'ETag': '"v2"'})
    key = _key('GET', 'https://example.com/acond')
    backend.set(key, entry)
    session = AsyncCachedSession(backend=backend, cache_control=True, always_revalidate=True)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'', 'https://example.com/acond', status=304))
    resp = await session.request('GET', 'https://example.com/acond')
    assert resp.content == b'original'
    refreshed = backend.get(key)
    assert refreshed is not None
    assert refreshed['ts'] >= entry['ts']


async def test_async_cached_session_cache_control_attaches_validators(
        mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'cached',
                   'https://example.com/aval',
                   headers={
                       'ETag': '"ae1"',
                       'Last-Modified': 'Mon, 01 Jan 2024 00:00:00 GMT'
                   })
    key = _key('GET', 'https://example.com/aval')
    backend.set(key, entry)
    session = AsyncCachedSession(backend=backend, cache_control=True, always_revalidate=True)
    parent = mocker.patch.object(niquests.AsyncSession,
                                 'request',
                                 return_value=_mock_resp(b'new', 'https://example.com/aval'))
    await session.request('GET', 'https://example.com/aval')
    call_kwargs = parent.call_args[1]
    assert call_kwargs['headers']['If-None-Match'] == '"ae1"'
    assert call_kwargs['headers']['If-Modified-Since'] == 'Mon, 01 Jan 2024 00:00:00 GMT'


def test_cached_session_always_revalidate_without_cache_control(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'cached', 'https://example.com/reval', headers={'ETag': '"v1"'})
    key = _key('GET', 'https://example.com/reval')
    backend.set(key, entry)
    session = CachedSession(backend=backend, always_revalidate=True, cache_control=False)
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'new', 'https://example.com/reval'))
    session.request('GET', 'https://example.com/reval')
    call_kwargs = parent.call_args[1]
    assert 'If-None-Match' not in call_kwargs.get('headers', {})
    assert 'If-Modified-Since' not in call_kwargs.get('headers', {})


def test_cached_session_cache_control_etag_only(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'cached', 'https://example.com/etag', headers={'ETag': '"e-only"'})
    key = _key('GET', 'https://example.com/etag')
    backend.set(key, entry)
    session = CachedSession(backend=backend, cache_control=True, always_revalidate=True)
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'new', 'https://example.com/etag'))
    session.request('GET', 'https://example.com/etag')
    call_kwargs = parent.call_args[1]
    assert call_kwargs['headers']['If-None-Match'] == '"e-only"'
    assert 'If-Modified-Since' not in call_kwargs['headers']


def test_cached_session_expired_entry_attaches_validators(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'stale',
                   'https://example.com/exp-val',
                   ts_offset=-100,
                   headers={'ETag': '"old"'})
    key = _key('GET', 'https://example.com/exp-val')
    backend.set(key, entry)
    session = CachedSession(backend=backend, expire_after=1, cache_control=True)
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'fresh', 'https://example.com/exp-val'))
    session.request('GET', 'https://example.com/exp-val')
    call_kwargs = parent.call_args[1]
    assert call_kwargs['headers']['If-None-Match'] == '"old"'


def test_cached_session_304_with_force_refresh_returns_304(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'original', 'https://example.com/fr304', headers={'ETag': '"v1"'})
    key = _key('GET', 'https://example.com/fr304')
    backend.set(key, entry)
    session = CachedSession(backend=backend, cache_control=True)
    mocker.patch.object(niquests.Session,
                        'request',
                        return_value=_mock_resp(b'', 'https://example.com/fr304', status=304))
    resp = session.request('GET', 'https://example.com/fr304', force_refresh=True)
    assert resp.status_code == 304


def test_cached_session_case_insensitive_validator_headers(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'cached',
                   'https://example.com/ci',
                   headers={
                       'etag': '"lower"',
                       'last-modified': 'Mon, 01 Jan 2024 00:00:00 GMT'
                   })
    key = _key('GET', 'https://example.com/ci')
    backend.set(key, entry)
    session = CachedSession(backend=backend, cache_control=True, always_revalidate=True)
    parent = mocker.patch.object(niquests.Session,
                                 'request',
                                 return_value=_mock_resp(b'new', 'https://example.com/ci'))
    session.request('GET', 'https://example.com/ci')
    call_kwargs = parent.call_args[1]
    assert call_kwargs['headers']['If-None-Match'] == '"lower"'
    assert call_kwargs['headers']['If-Modified-Since'] == 'Mon, 01 Jan 2024 00:00:00 GMT'


async def test_async_cached_session_304_with_force_refresh(mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'original', 'https://example.com/afr304', headers={'ETag': '"v1"'})
    key = _key('GET', 'https://example.com/afr304')
    backend.set(key, entry)
    session = AsyncCachedSession(backend=backend, cache_control=True)
    mocker.patch.object(niquests.AsyncSession,
                        'request',
                        return_value=_mock_resp(b'', 'https://example.com/afr304', status=304))
    resp = await session.request('GET', 'https://example.com/afr304', force_refresh=True)
    assert resp.status_code == 304


async def test_async_cached_session_expired_entry_attaches_validators(
        mocker: MockerFixture) -> None:
    backend = MemoryBackend()
    entry = _entry(b'stale',
                   'https://example.com/aexp-val',
                   ts_offset=-100,
                   headers={'ETag': '"old"'})
    key = _key('GET', 'https://example.com/aexp-val')
    backend.set(key, entry)
    session = AsyncCachedSession(backend=backend, expire_after=1, cache_control=True)
    parent = mocker.patch.object(niquests.AsyncSession,
                                 'request',
                                 return_value=_mock_resp(b'fresh', 'https://example.com/aexp-val'))
    await session.request('GET', 'https://example.com/aexp-val')
    call_kwargs = parent.call_args[1]
    assert call_kwargs['headers']['If-None-Match'] == '"old"'
