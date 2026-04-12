local utils = import 'utils.libsonnet';

{
  uses_user_defaults: true,
  project_name: 'niquests-cache',
  description: 'Filesystem-cached niquests sessions.',
  keywords: ['cache', 'filesystem', 'http', 'niquests'],
  python_deps+: {
    main+: {
      niquests: utils.latestPypiPackageVersionCaret('niquests'),
      platformdirs: utils.latestPypiPackageVersionCaret('platformdirs'),
    },
    tests+: {
      'pytest-asyncio': utils.latestPypiPackageVersionCaret('pytest-asyncio'),
    },
  },
  pyproject+: {
    tool+: {
      pytest+: {
        ini_options+: {
          asyncio_mode: 'auto',
        },
      },
    },
  },
}
