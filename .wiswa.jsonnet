local utils = import 'utils.libsonnet';

{
  uses_user_defaults: true,
  project_name: 'niquests-cache',
  version: '0.2.1',
  description: 'Cached niquests sessions with pluggable storage backends.',
  keywords: ['cache', 'filesystem', 'http', 'niquests'],
  python_deps+: {
    main+: {
      aiosqlite: utils.latestPypiPackageVersionCaret('aiosqlite'),
      anyio: utils.latestPypiPackageVersionCaret('anyio'),
      niquests: utils.latestPypiPackageVersionCaret('niquests'),
      platformdirs: utils.latestPypiPackageVersionCaret('platformdirs'),
    },
    tests+: {
      'pytest-asyncio': utils.latestPypiPackageVersionCaret('pytest-asyncio'),
    },
  },
  pyproject+: {
    tool+: {
      coverage+: {
        report+: {
          omit+: ['niquests_cache/typing.py'],
        },
        run+: {
          omit+: ['niquests_cache/typing.py'],
        },
      },
      pytest+: {
        ini_options+: {
          asyncio_mode: 'auto',
        },
      },
    },
  },
}
