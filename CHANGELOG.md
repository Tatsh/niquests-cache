<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.1/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

## [0.0.1] - 2026-04-11

### Added

- `CachedSession` and `CachedAsyncSession` for filesystem-backed caching of successful `GET` and
  `HEAD` responses.
- `cached_session()` helper with optional `app_name` (for `platformdirs.user_cache_path`), `aio`,
  `no_cache`, and `expire_after`.

[unreleased]: https://github.com/Tatsh/niquests-cache/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/Tatsh/niquests-cache/releases/tag/v0.0.1
