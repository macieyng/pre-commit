from __future__ import annotations

import os
import sys
from unittest import mock

import pytest

import pre_commit.constants as C
from pre_commit.languages import pipenv
from pre_commit.prefix import Prefix
from pre_commit.util import cmd_output
from testing.language_helpers import run_language

def test_health_check_no_pipfile(tmp_path):
    with pytest.raises(AssertionError) as excinfo:
        pipenv.health_check(Prefix(str(tmp_path)), C.DEFAULT)
    assert '`language: pipenv` requires a Pipfile' in str(excinfo.value)

def _make_pipfile(path):
    with open(os.path.join(path, 'Pipfile'), 'w') as f:
        f.write('''\
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
requests = "*"

[dev-packages]
pytest = "*"

[requires]
python_version = "3.9"
''')

def test_health_check_with_pipfile(tmp_path):
    _make_pipfile(tmp_path)
    with mock.patch.object(pipenv, 'cmd_output_b') as mocked:
        # Mock os.path.exists to simulate virtualenv not existing then existing
        exists_calls = {
            os.path.join(str(tmp_path), 'Pipfile'): True,
        }
        def mock_exists(path):
            if path.endswith('pipenv_env-default'):
                exists_calls[path] = exists_calls.get(path, False)
                return exists_calls[path]
            return exists_calls.get(path, False)
        
        with mock.patch.object(os.path, 'exists', side_effect=mock_exists):
            assert pipenv.health_check(Prefix(str(tmp_path)), C.DEFAULT) is None
            
            # Should have two calls: one to create virtualenv, one to check
            assert len(mocked.call_args_list) == 2
            
            # First call should be to create virtualenv
            assert mocked.call_args_list[0][0] == ('pipenv', '--python', f"{sys.version_info[0]}.{sys.version_info[1]}")
            assert mocked.call_args_list[0][1]['env']['PIPENV_IGNORE_VIRTUALENVS'] == '1'
            assert mocked.call_args_list[0][1]['env']['PIPENV_VERBOSITY'] == '-1'
            assert mocked.call_args_list[0][1]['cwd'] == str(tmp_path)
            
            # Second call should be the health check
            assert mocked.call_args_list[1][0] == ('pipenv', 'check')
            assert mocked.call_args_list[1][1]['env']['PIPENV_IGNORE_VIRTUALENVS'] == '1'
            assert mocked.call_args_list[1][1]['env']['PIPENV_VERBOSITY'] == '-1'
            assert mocked.call_args_list[1][1]['cwd'] == str(tmp_path)

def test_install_environment(tmp_path):
    _make_pipfile(tmp_path)
    
    with mock.patch.object(pipenv, 'cmd_output_b') as mocked:
        pipenv.install_environment(
            Prefix(str(tmp_path)), 
            C.DEFAULT, 
            ['black']
        )
        
        python_version = f"{sys.version_info[0]}.{sys.version_info[1]}"
        assert len(mocked.call_args_list) == 3
        
        # Check first call - pipenv --python
        assert mocked.call_args_list[0][0] == ('pipenv', '--python', python_version)
        assert mocked.call_args_list[0][1]['env']['PIPENV_IGNORE_VIRTUALENVS'] == '1'
        assert mocked.call_args_list[0][1]['env']['PIPENV_VERBOSITY'] == '-1'
        assert mocked.call_args_list[0][1]['cwd'] == str(tmp_path)
        
        # Check second call - pipenv install --dev
        assert mocked.call_args_list[1][0] == ('pipenv', 'install', '--dev')
        assert mocked.call_args_list[1][1]['env']['PIPENV_IGNORE_VIRTUALENVS'] == '1'
        assert mocked.call_args_list[1][1]['env']['PIPENV_VERBOSITY'] == '-1'
        assert mocked.call_args_list[1][1]['cwd'] == str(tmp_path)
        
        # Check third call - pipenv install black
        assert mocked.call_args_list[2][0] == ('pipenv', 'install', 'black')
        assert mocked.call_args_list[2][1]['env']['PIPENV_IGNORE_VIRTUALENVS'] == '1'
        assert mocked.call_args_list[2][1]['env']['PIPENV_VERBOSITY'] == '-1'
        assert mocked.call_args_list[2][1]['cwd'] == str(tmp_path)

@pytest.fixture
def mock_cmd_output_b():
    with mock.patch.object(pipenv, 'cmd_output_b') as mocked:
        def mock_cmd(*args, **kwargs):
            if args[0] == 'pipenv':
                if args[1] == 'run':
                    return 0, b'Hello from pipenv!\n', None
                return 0, b'', None
            return 0, b'', None
        mocked.side_effect = mock_cmd
        yield mocked

def test_run_hook(tmp_path, mock_cmd_output_b):
    _make_pipfile(tmp_path)
    
    # Create a simple Python script
    script = '''\
#!/usr/bin/env python
print("Hello from pipenv!")
'''
    tmp_path.joinpath('script.py').write_text(script)
    
    ret = run_language(
        tmp_path,
        pipenv,
        'python script.py',  # Don't include pipenv run, it's added by the language
    )
    assert ret == (0, b'Hello from pipenv!\n') 