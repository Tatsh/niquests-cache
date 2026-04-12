<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.1/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

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

[unreleased]: https://github.com/Tatsh/niquests-cache/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/Tatsh/niquests-cache/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/Tatsh/niquests-cache/releases/tag/v0.0.1
