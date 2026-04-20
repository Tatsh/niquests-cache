<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.1/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

## [0.2.1] - 2026-04-20

### Added

- Conditional revalidation support in `CachedSession` and `AsyncCachedSession`: when
  `cache_control=True`, outbound requests include `If-None-Match` and `If-Modified-Since` headers
  derived from the cached entry's `ETag` and `Last-Modified` values.
- 304 Not Modified handling: a 304 response now refreshes the cached entry's timestamp instead of
  replacing it, and the original cached response is returned to the caller.
- `always_revalidate` setting: when enabled, every request with a cached entry sends a conditional
  request to the origin server, bypassing the TTL-based cache-hit path.

### Changed

- `If-Modified-Since` and `If-None-Match` are now included in the default ignored parameters list
  so conditional headers do not affect cache keys.

## [0.2.0] - 2026-04-18

### Removed

- `JsonSerializer` deprecated subclass from `niquests_cache.serializers`. Use `JSONSerializer`
  instead.

## [0.1.1] - 2026-04-18

### Changed

- Renamed `JsonSerializer` to `JSONSerializer` in `niquests_cache.serializers`.

### Deprecated

- `JsonSerializer` remains as a subclass of `JSONSerializer` and emits a `DeprecationWarning` on
  instantiation. Use `JSONSerializer` instead.

## [0.1.0] - 2026-04-18

### Added

- Pluggable storage backends in `niquests_cache.backends`: `BaseBackend` ABC, `FileCache`,
  `MemoryBackend`, and `SQLiteBackend`.
- Serializers in `niquests_cache.serializers`: `JsonSerializer` (default, base64-encodes binary
  content) and `PickleSerializer`. Custom serializers are supported via a duck-typed `dumps`/`loads`
  protocol.
- `CacheSettings` dataclass exposing all session settings as a mutable `session.settings`
  attribute.
- `CacheMixin` public mixin class for subclassing.
- `cache_disabled()` context manager (sync and async variants) to temporarily bypass the cache.
- `session.cache` and `session.backend` properties on cached sessions.
- Per-request keyword arguments `only_if_cached`, `refresh`, and `force_refresh` on `request()`.
- `CachedSession` and `AsyncCachedSession` now accept the full requests-cache-style API:
  positional `cache_name` and `backend`, plus keyword `serializer`, `expire_after`,
  `urls_expire_after`, `cache_control`, `content_root_key`, `allowable_codes`,
  `allowable_methods`, `always_revalidate`, `ignored_parameters`, `match_headers`, `filter_fn`,
  `key_fn`, `read_only`, `stale_if_error`, and `autoclose`.
- Debug logging of the selected backend at session construction.
- New runtime dependencies: `aiosqlite>=0.20` and `anyio>=4.4`.
- `cached_session()` helper accepts a `backend=` keyword argument (a
  `~niquests_cache.backends.BaseBackend` instance or a built-in alias).
- `BackendAlias` type alias in `niquests_cache.typing` for the literal set
  `'sqlite' | 'memory' | 'filesystem'`.
- `SQLiteBackend.close()` method to deterministically close the underlying SQLite connection
  (also invoked automatically when the backend is garbage collected).

### Changed

- Default storage backend is now SQLite (was filesystem). The SQLite backend stores entries in
  typed columns (`key`, `content` as `BLOB`, `encoding`, `headers` JSON, `status_code`, `ts`,
  `url`) and handles binary responses natively.
- `FileCache` matches the requests-cache `FileCache` API: `cache_name`, `use_temp`,
  `use_cache_dir`, `extension`, `lock`, and `serializer`. Asynchronous `aget`/`aset` use anyio for
  non-blocking I/O.
- `AsyncCachedSession` uses aiosqlite for SQLite and anyio for filesystem backends.
- `CacheEntry.content` is now `bytes` (was `str`) to support binary responses.
- Cache key now incorporates the request method, the URL (with `ignored_parameters` stripped),
  and optional request headers (per the `match_headers` setting).
- Renamed `CachedAsyncSession` to `AsyncCachedSession`.
- The top-level package re-exports only `AsyncCachedSession`, `CachedSession`, and
  `cached_session`. Other types are accessed via submodules (`niquests_cache.backends`,
  `niquests_cache.serializers`, `niquests_cache.settings`, `niquests_cache.typing`).
- Project description updated to "Cached niquests sessions with pluggable storage backends."

### Fixed

- Decode `bytes`-typed response header values to `str` before populating the cache entry so the
  entry round-trips through the JSON serializer cleanly.

### Removed

- `CachedAsyncSession` alias (replaced by `AsyncCachedSession`).

## [0.0.3] - 2026-04-11

### Changed

- `cached_session` overloads for a generic `no_cache` `bool` so type checkers return the same session
  unions as the implementation.

## [0.0.2] - 2026-04-11

### Added

- Overloads for the `cached_session` factory for clearer type narrowing.

### Changed

- Sphinx documentation: intersphinx mappings for Niquests and platformdirs.
- Normalised `cached_session` docstring parameter markup.

### Fixed

- Tests: `user_cache_path` mocks no longer treat a `MagicMock` as a directory path.

## [0.0.1] - 2026-04-11

### Added

- `CachedSession` and `CachedAsyncSession` for filesystem-backed caching of successful `GET` and
  `HEAD` responses.
- `cached_session()` helper with optional `app_name` (for `platformdirs.user_cache_path`), `aio`,
  `no_cache`, and `expire_after`.

[unreleased]: https://github.com/Tatsh/niquests-cache/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Tatsh/niquests-cache/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Tatsh/niquests-cache/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Tatsh/niquests-cache/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Tatsh/niquests-cache/compare/v0.0.3...v0.1.0
[0.0.3]: https://github.com/Tatsh/niquests-cache/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/Tatsh/niquests-cache/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/Tatsh/niquests-cache/releases/tag/v0.0.1
