from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Generator
from collections.abc import Sequence

import pre_commit.constants as C
from pre_commit import lang_base
from pre_commit.envcontext import envcontext
from pre_commit.languages import python
from pre_commit.prefix import Prefix
from pre_commit.util import cmd_output_b

ENVIRONMENT_DIR = 'pipenv_env'
get_default_version = python.get_default_version


def _find_pipfile(start_dir: str) -> str | None:
    """Search for Pipfile starting from start_dir and moving up."""
    current = os.path.abspath(start_dir)
    while True:
        pipfile = os.path.join(current, 'Pipfile')
        if os.path.exists(pipfile):
            return pipfile
        parent = os.path.dirname(current)
        if parent == current:  # Reached root directory
            break
        current = parent
    return None


def _assert_pipfile_exists(prefix: Prefix) -> str:
    """Assert Pipfile exists and return its directory path."""
    pipfile = _find_pipfile(prefix.prefix_dir)
    if not pipfile:
        raise AssertionError(
            '`language: pipenv` requires a Pipfile in the repository',
        )
    return os.path.dirname(pipfile)


def _get_env_with_pipenv_settings() -> dict[str, str]:
    # Force pipenv to create its own virtualenv
    env = dict(os.environ)
    env['PIPENV_IGNORE_VIRTUALENVS'] = '1'
    env['PIPENV_VERBOSITY'] = '-1'  # Suppress warnings
    return env


def _ensure_virtualenv(prefix: Prefix, version: str) -> None:
    directory = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    if not os.path.exists(directory):
        python_version = (
            version if version != C.DEFAULT
            else f'{sys.version_info[0]}.{sys.version_info[1]}'
        )
        pipfile_dir = _assert_pipfile_exists(prefix)
        cmd_output_b(
            'pipenv', '--python', python_version,
            env=_get_env_with_pipenv_settings(),
            cwd=pipfile_dir,
        )


def health_check(prefix: Prefix, version: str) -> str | None:
    try:
        pipfile_dir = _assert_pipfile_exists(prefix)
        _ensure_virtualenv(prefix, version)
        with in_env(prefix, version):
            cmd_output_b(
                'pipenv', 'check',
                env=_get_env_with_pipenv_settings(),
                cwd=pipfile_dir,
            )
        return None
    except Exception as e:
        return f'pipenv environment check failed: {e}'


@contextlib.contextmanager
def in_env(prefix: Prefix, version: str) -> Generator[None]:
    directory = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    env = python.get_env_patch(directory)
    with envcontext(env):
        yield


def install_environment(
        prefix: Prefix,
        version: str,
        additional_dependencies: Sequence[str],
) -> None:
    pipfile_dir = _assert_pipfile_exists(prefix)
    env = _get_env_with_pipenv_settings()

    _ensure_virtualenv(prefix, version)

    with in_env(prefix, version):
        # Install dependencies from Pipfile
        cmd_output_b(
            'pipenv', 'install', '--dev',
            env=env,
            cwd=pipfile_dir,
        )

        # Install additional dependencies if specified
        if additional_dependencies:
            cmd_output_b(
                'pipenv', 'install', *additional_dependencies,
                env=env,
                cwd=pipfile_dir,
            )


def run_hook(
        prefix: Prefix,
        entry: str,
        args: Sequence[str],
        file_args: Sequence[str],
        *,
        is_local: bool,
        require_serial: bool,
        color: bool,
) -> tuple[int, bytes]:
    env = _get_env_with_pipenv_settings()
    cmd = ('pipenv', 'run', entry, *args)
    pipfile_dir = _assert_pipfile_exists(prefix)
    with in_env(prefix, C.DEFAULT):
        if file_args:
            return lang_base.run_xargs(
                cmd,
                file_args,
                require_serial=require_serial,
                color=color,
            )
        else:
            ret, stdout, _ = cmd_output_b(*cmd, env=env, cwd=pipfile_dir)
            return ret, stdout
