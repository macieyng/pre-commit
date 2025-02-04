from __future__ import annotations

import os.path
from unittest import mock

import pre_commit.constants as C
from pre_commit.languages import pipenv
from pre_commit.prefix import Prefix

PIPFILE = '''\
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
requests = "*"

[dev-packages]
'''


def test_find_pipfile_in_current_dir(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    found = pipenv._find_pipfile(prefix.prefix_dir)
    assert found == str(pipfile)


def test_find_pipfile_in_parent_dir(tmp_path):
    # Create a parent directory with Pipfile
    parent_dir = tmp_path
    with open(parent_dir / 'Pipfile', 'w') as f:
        f.write(PIPFILE)

    # Create a subdirectory
    sub_dir = parent_dir / 'sub' / 'subsub'
    os.makedirs(sub_dir)

    # Search from subdirectory
    found = pipenv._find_pipfile(str(sub_dir))
    assert found == str(parent_dir / 'Pipfile')


def test_find_pipfile_not_found(tmp_path):
    # Create an empty directory structure
    sub_dir = tmp_path / 'sub' / 'subsub'
    os.makedirs(sub_dir)

    # Search from subdirectory
    found = pipenv._find_pipfile(str(sub_dir))
    assert found is None


def test_assert_pipfile_exists_uses_nearest_pipfile(tmp_path):
    # Create parent directory with Pipfile
    parent_dir = tmp_path
    with open(parent_dir / 'Pipfile', 'w') as f:
        f.write(PIPFILE)

    # Create subdirectory with its own Pipfile
    sub_dir = parent_dir / 'sub'
    os.makedirs(sub_dir)
    with open(sub_dir / 'Pipfile', 'w') as f:
        f.write(PIPFILE)

    # Create a deeper subdirectory
    work_dir = sub_dir / 'work'
    os.makedirs(work_dir)

    # Verify it finds the nearest Pipfile
    prefix = Prefix(str(work_dir))
    pipfile_dir = pipenv._assert_pipfile_exists(prefix)
    assert pipfile_dir == str(sub_dir)


def test_health_check_with_pipfile(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        with mock.patch.object(os.path, 'exists', return_value=True):
            assert pipenv.health_check(prefix, C.DEFAULT) is None

    cmd_output_b_mock.assert_called_once_with(
        'pipenv', 'check',
        env=mock.ANY,
        cwd=prefix.prefix_dir,
    )


def test_health_check_without_pipfile(tmp_path):
    prefix = Prefix(str(tmp_path))

    paths_checked = []

    def mock_exists(path: str) -> bool:
        paths_checked.append(path)
        print(f'Checking path: {path}')
        # Return False for any path to simulate no Pipfile found
        return False

    with mock.patch.object(os.path, 'exists', side_effect=mock_exists):
        error = pipenv.health_check(prefix, C.DEFAULT)
        print(f'Paths checked: {paths_checked}')
        assert error == (
            'pipenv environment check failed: '
            '`language: pipenv` requires a Pipfile in the repository'
        )


def test_health_check_fails(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        cmd_output_b_mock.side_effect = RuntimeError('pipenv check failed')
        with mock.patch.object(os.path, 'exists', return_value=True):
            error = pipenv.health_check(prefix, C.DEFAULT)
            assert error == (
                'pipenv environment check failed: pipenv check failed'
            )


def test_ensure_virtualenv_fails(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    def mock_exists(path: str) -> bool:
        if path.endswith('Pipfile'):
            return True
        return True  # Cover the default case

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        cmd_output_b_mock.side_effect = RuntimeError('pipenv creation failed')
        with mock.patch.object(os.path, 'exists', side_effect=mock_exists):
            error = pipenv.health_check(prefix, C.DEFAULT)
            assert error == (
                'pipenv environment check failed: pipenv creation failed'
            )


def test_ensure_virtualenv_with_version(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    def mock_exists(path: str) -> bool:
        if path.endswith('Pipfile'):
            return True
        return False

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        with mock.patch.object(os.path, 'exists', side_effect=mock_exists):
            pipenv._ensure_virtualenv(prefix, '3.9')

    cmd_output_b_mock.assert_called_once_with(
        'pipenv', '--python', '3.9',
        env=mock.ANY,
        cwd=os.path.dirname(str(pipfile)),
    )


def test_install_environment_with_additional_deps(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        with mock.patch.object(os.path, 'exists', return_value=True):
            pipenv.install_environment(prefix, C.DEFAULT, ['black==22.3.0'])

    assert cmd_output_b_mock.call_count == 2
    cmd_output_b_mock.assert_has_calls([
        mock.call(
            'pipenv', 'install', '--dev',
            env=mock.ANY,
            cwd=prefix.prefix_dir,
        ),
        mock.call(
            'pipenv', 'install', 'black==22.3.0',
            env=mock.ANY,
            cwd=prefix.prefix_dir,
        ),
    ])


def test_install_environment_without_additional_deps(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        with mock.patch.object(os.path, 'exists', return_value=True):
            pipenv.install_environment(prefix, C.DEFAULT, ())

    cmd_output_b_mock.assert_called_once_with(
        'pipenv', 'install', '--dev',
        env=mock.ANY,
        cwd=prefix.prefix_dir,
    )


def test_run_hook_without_file_args(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        cmd_output_b_mock.return_value = (0, b'Hello from pipenv!\n', b'')
        with mock.patch.object(os.path, 'exists', return_value=True):
            ret = pipenv.run_hook(
                prefix,
                'black',
                ['--check'],
                (),
                is_local=True,
                require_serial=True,
                color=True,
            )

    assert ret == (0, b'Hello from pipenv!\n')
    cmd_output_b_mock.assert_called_once_with(
        'pipenv', 'run', 'black', '--check',
        env=mock.ANY,
        cwd=os.path.dirname(str(pipfile)),
    )


def test_run_hook_with_file_args(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv.lang_base, 'run_xargs') as run_xargs_mock:
        run_xargs_mock.return_value = (0, b'Hello from pipenv!\n')
        ret = pipenv.run_hook(
            prefix,
            'black',
            ['--check'],
            ('file1.py', 'file2.py'),
            is_local=True,
            require_serial=True,
            color=True,
        )

    assert ret == (0, b'Hello from pipenv!\n')
    run_xargs_mock.assert_called_once_with(
        ('pipenv', 'run', 'black', '--check'),
        ('file1.py', 'file2.py'),
        require_serial=True,
        color=True,
    )


def test_install_environment_with_packages(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        with mock.patch.object(os.path, 'exists', return_value=True):
            pipenv.install_environment(prefix, C.DEFAULT, [])

    cmd_output_b_mock.assert_has_calls([
        mock.call(
            'pipenv', 'install', '--dev',
            env=mock.ANY,
            cwd=os.path.dirname(str(pipfile)),
        ),
    ])
