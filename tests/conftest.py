'''Shared fixtures for the csvv tests.'''

import importlib.machinery
import importlib.util
import pathlib
import subprocess
import sys
import types
from collections.abc import Callable

import pytest

CSVV = pathlib.Path(__file__).resolve().parent.parent / 'csvv'

type Run = Callable[..., subprocess.CompletedProcess[bytes]]


@pytest.fixture(name='csvv', scope='session')
def fixture_csvv() -> types.ModuleType:
    '''Import the csvv script as a module, which needs a loader since it has no .py suffix.'''

    loader = importlib.machinery.SourceFileLoader('csvv', str(CSVV))
    spec = importlib.util.spec_from_loader('csvv', loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks the module up in sys.modules while building a class.
    sys.modules['csvv'] = module
    loader.exec_module(module)
    return module


@pytest.fixture(name='run')
def fixture_run() -> Run:
    '''Return a function that runs csvv with args, feeding it stdin as bytes.'''

    def run(*args: str, stdin: bytes = b'') -> subprocess.CompletedProcess[bytes]:
        return subprocess.run([sys.executable, str(CSVV), *args], input=stdin,
                              capture_output=True, check=False)

    return run
