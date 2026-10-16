'''Shared fixtures for the csvv tests.'''

import pathlib
import subprocess
import sys
from collections.abc import Callable

import pytest

CSVV = pathlib.Path(__file__).resolve().parent.parent / 'csvv'

type Run = Callable[..., subprocess.CompletedProcess[bytes]]


@pytest.fixture(name='run')
def fixture_run() -> Run:
    '''Return a function that runs csvv with args, feeding it stdin as bytes.'''

    def run(*args: str, stdin: bytes = b'') -> subprocess.CompletedProcess[bytes]:
        return subprocess.run([sys.executable, str(CSVV), *args], input=stdin,
                              capture_output=True, check=False)

    return run
