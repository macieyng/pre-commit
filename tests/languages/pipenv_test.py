from __future__ import annotations

import os.path
from unittest import mock

import pytest

import pre_commit.constants as C
from pre_commit.languages import pipenv
from pre_commit.prefix import Prefix

PIPFILE = '''\
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]

[dev-packages]
'''


@pytest.fixture
def find_pipenv_env(tmp_path):
    ret = tmp_path.joinpath('pipenv_env')
    with mock.patch.object(
        pipenv.lang_base, 'environment_dir',
        return_value=str(ret),
    ):
        yield ret


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
    with pytest.raises(AssertionError) as excinfo:
        pipenv.health_check(prefix, C.DEFAULT)
    msg, = excinfo.value.args
    assert msg == '`language: pipenv` requires a Pipfile in the repository'


def test_run_hook(tmp_path):
    prefix = Prefix(str(tmp_path))
    pipfile = prefix.path('Pipfile')
    with open(pipfile, 'w') as f:
        f.write(PIPFILE)

    with mock.patch.object(pipenv, 'cmd_output_b') as cmd_output_b_mock:
        cmd_output_b_mock.return_value = (0, b'Hello from pipenv!\n', b'')
        ret = pipenv.run_hook(
            prefix, 'python script.py', (), (),
            is_local=False,
            require_serial=False,
            color=False,
        )

    assert ret == (0, b'Hello from pipenv!\n')
    cmd_output_b_mock.assert_called_once_with(
        'pipenv', 'run', 'python script.py',
        env=mock.ANY,
        cwd=prefix.prefix_dir,
    )
