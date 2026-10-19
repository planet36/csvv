'''Tests for reading and writing CSV, with no filter, sort, or select.'''

# A test's name says what it checks.
# pylint: disable=missing-function-docstring

import csv
import errno
import io
import itertools
import os
import signal
import subprocess
import sys
import types
from collections.abc import Iterator

import pytest

from conftest import CSVV, Run


def parse(data: bytes, delimiter: str = ',') -> list[list[str]]:
    '''Parse data as CSV, for comparing values where the quoting may differ.'''
    text = data.decode('utf-8', errors='surrogateescape')
    return list(csv.reader(io.StringIO(text, newline=''), delimiter=delimiter))


@pytest.mark.parametrize('data', [
    pytest.param(b'a,b\n1,2\n', id='plain'),
    pytest.param(b'a,b\n"x,y",2\n', id='quoted comma'),
    pytest.param(b'a,b\n"say ""hi""",2\n', id='doubled quote'),
    pytest.param(b'a,b\n"line\nbreak",2\n', id='embedded newline'),
    pytest.param(b'a,a\n1,2\n', id='duplicate header'),
    pytest.param(b'a\n""\n', id='lone empty field'),
    pytest.param(b'a,b\n,\n', id='empty fields'),
    pytest.param('a,b\n日本,é\n'.encode(), id='non-ascii'),
    pytest.param(b'a,b\n\xff\xfe,2\n', id='invalid utf-8'),
    pytest.param(b'a,b\n007,1e5\n', id='number-like text'),
])
def test_round_trip_is_byte_identical(run: Run, data: bytes) -> None:
    for args in ((), ('-H',)):
        result = run(*args, stdin=data)
        assert result.returncode == 0, result.stderr
        assert result.stdout == data


@pytest.mark.parametrize(('data', 'expected'), [
    pytest.param(b'"a","b"\n"1",2\n', b'a,b\n1,2\n', id='needless quotes'),
    pytest.param(b'a,b\n12" pipe,2\n', b'a,b\n"12"" pipe",2\n', id='quote mid-field'),
])
def test_round_trip_keeps_values_when_quoting_changes(run: Run, data: bytes,
                                                      expected: bytes) -> None:
    result = run(stdin=data)
    assert result.stdout == expected
    assert parse(result.stdout) == parse(data)


def test_crlf_becomes_lf(run: Run) -> None:
    result = run(stdin=b'a,b\r\n"x\r\ny",2\r\n')
    assert result.stdout == b'a,b\n"x\r\ny",2\n'


def test_bom_is_dropped(run: Run) -> None:
    result = run('-H', stdin=b'\xef\xbb\xbfid,v\n1,2\n')
    assert result.stdout == b'id,v\n1,2\n'


def test_field_over_default_size_limit(run: Run) -> None:
    big = b'x' * 200_000
    result = run(stdin=b'a,' + big + b'\n')
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'a,' + big + b'\n'


def test_empty_input(run: Run) -> None:
    for args in ((), ('-H',)):
        result = run(*args, stdin=b'')
        assert (result.returncode, result.stdout, result.stderr) == (0, b'', b'')


def test_header_only(run: Run) -> None:
    result = run('-H', stdin=b'a,b\n')
    assert (result.returncode, result.stdout) == (0, b'a,b\n')


def test_blank_lines_are_skipped(run: Run) -> None:
    result = run(stdin=b'a,b\n\n1,2\n\n')
    assert (result.returncode, result.stdout) == (0, b'a,b\n1,2\n')


def test_file_argument(run: Run, tmp_path) -> None:
    path = tmp_path / 'in.csv'
    path.write_bytes(b'\xef\xbb\xbfa,b\r\n1,2\r\n')
    result = run(str(path))
    assert (result.returncode, result.stdout) == (0, b'a,b\n1,2\n')


def test_dash_means_stdin(run: Run) -> None:
    assert run('-', stdin=b'a\n').stdout == b'a\n'


def test_missing_file(run: Run, tmp_path) -> None:
    path = tmp_path / 'missing.csv'
    result = run(str(path))
    assert result.returncode == 1
    assert result.stderr == f'csvv: {path}: No such file or directory\n'.encode()


def test_failed_read_names_the_source(csvv: types.ModuleType) -> None:
    def lines() -> Iterator[str]:
        yield 'a,b\n'
        yield '1,2\n'
        raise OSError(errno.EIO, os.strerror(errno.EIO))

    records = csvv.read_records(lines(), ',', 'in.csv')
    assert [r.row for r in itertools.islice(records, 2)] == [['a', 'b'], ['1', '2']]
    with pytest.raises(csvv.DataError) as e:
        next(records)
    assert str(e.value) == 'in.csv: record 3, line 3: Input/output error'


@pytest.mark.skipif(not os.path.exists('/proc/self/mem'), reason='needs /proc/self/mem')
def test_failed_read_is_not_a_failed_write(run: Run) -> None:
    # Reading /proc/self/mem from offset 0 fails with EIO, since that
    # address is never mapped.
    result = run('/proc/self/mem')
    assert result.returncode == 1
    assert result.stderr == b'csvv: /proc/self/mem: record 1, line 1: Input/output error\n'


def test_ragged_short_row_is_an_error(run: Run) -> None:
    result = run(stdin=b'a,b,c\n1,2,3\n4,5\n')
    assert result.returncode == 1
    assert result.stderr == b'csvv: stdin: record 3, line 3: expected 3 fields, found 2\n'
    assert result.stdout == b'a,b,c\n1,2,3\n'


def test_ragged_long_row_is_an_error(run: Run) -> None:
    result = run(stdin=b'a,b\n1,2,3\n')
    assert result.returncode == 1
    assert b'record 2, line 2: expected 2 fields, found 3' in result.stderr


def test_ragged_error_names_the_starting_line(run: Run) -> None:
    result = run(stdin=b'a,b\n"x\ny",2\n\n1\n')
    assert result.stderr == b'csvv: stdin: record 3, line 5: expected 2 fields, found 1\n'


def test_ragged_pad(run: Run) -> None:
    result = run('--ragged', 'pad', stdin=b'a,b,c\n1\n')
    assert (result.returncode, result.stdout) == (0, b'a,b,c\n1,,\n')


def test_ragged_pad_still_rejects_a_long_row(run: Run) -> None:
    assert run('--ragged', 'pad', stdin=b'a\n1,2\n').returncode == 1


def test_ragged_truncate(run: Run) -> None:
    result = run('--ragged', 'truncate', stdin=b'a,b\n1,2,3\n')
    assert (result.returncode, result.stdout) == (0, b'a,b\n1,2\n')


def test_ragged_truncate_still_rejects_a_short_row(run: Run) -> None:
    assert run('--ragged', 'truncate', stdin=b'a,b\n1\n').returncode == 1


def test_ragged_width_comes_from_the_header(run: Run) -> None:
    result = run('-H', '--ragged', 'pad', stdin=b'a,b\n1\n')
    assert result.stdout == b'a,b\n1,\n'


@pytest.mark.parametrize(('data', 'message'), [
    pytest.param(b'a,b\n"x" y,2\n', b'record 2, line 2: \',\' expected after \'"\'',
                 id='text after closing quote'),
    pytest.param(b'a,b\n"open,2\nmore\n', b'record 2, line 2: unexpected end of data',
                 id='unclosed quote'),
])
def test_malformed_csv_is_an_error(run: Run, data: bytes, message: bytes) -> None:
    result = run(stdin=data)
    assert result.returncode == 1
    assert message in result.stderr


def test_input_delimiter(run: Run) -> None:
    result = run('-F', ';', stdin=b'a;"b;c"\n1;2\n')
    assert result.stdout == b'a;"b;c"\n1;2\n'


def test_output_delimiter_converts(run: Run) -> None:
    result = run('-F', ';', '-o', ',', stdin=b'a;b,c\n1;2\n')
    assert result.stdout == b'a,"b,c"\n1,2\n'


def test_tab_escape(run: Run) -> None:
    result = run('-o', r'\t', stdin=b'a,b\n"x\ty",2\n')
    assert result.stdout == b'a\tb\n"x\ty"\t2\n'
    assert run('-F', r'\t', stdin=b'a\tb\n').stdout == b'a\tb\n'


@pytest.mark.parametrize('value', ['ab', '', '"', '\n'])
def test_bad_delimiter_is_a_usage_error(run: Run, value: str) -> None:
    for option in ('-F', '-o'):
        result = run(option, value)
        assert result.returncode == 2
        assert option.encode() in result.stderr


def test_bad_ragged_mode_is_a_usage_error(run: Run) -> None:
    assert run('--ragged', 'skip').returncode == 2


def test_version(run: Run) -> None:
    result = run('-V')
    assert result.returncode == 0
    lines = result.stdout.decode().splitlines()
    assert lines[0].startswith('csvv 20')
    assert lines[1:] == ['Copyright Steven Ward', '', 'License: MPL-2.0', '',
                         'Written by Steven Ward']


def test_help(run: Run) -> None:
    result = run('-h')
    assert result.returncode == 0
    assert result.stdout.startswith(b'usage: csvv [OPTION]... [FILE]')


def test_broken_pipe_is_silent(tmp_path) -> None:
    # The input comes from a file, because writing it to stdin while csvv
    # blocks on a full stdout would deadlock.
    path = tmp_path / 'big.csv'
    path.write_bytes(b'a,b\n' * 200_000)
    with subprocess.Popen([sys.executable, str(CSVV), str(path)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        assert proc.stdout is not None and proc.stderr is not None
        proc.stdout.readline()
        proc.stdout.close()
        stderr = proc.stderr.read()
        proc.wait()
    assert stderr == b''
    assert proc.returncode in (0, -signal.SIGPIPE)


@pytest.mark.skipif(not os.path.exists('/dev/full'), reason='needs /dev/full')
@pytest.mark.parametrize('lines', [1, 100_000])
def test_failed_write_is_reported_once(tmp_path, lines: int) -> None:
    # Small output fails only when it is flushed, and large output fails
    # while it is written.  Both must give csvv's message and status 1.
    path = tmp_path / 'in.csv'
    path.write_bytes(b'a,b\n' * lines)
    with open('/dev/full', 'wb') as full:
        result = subprocess.run([sys.executable, str(CSVV), str(path)], stdout=full,
                                stderr=subprocess.PIPE, check=False)
    assert result.returncode == 1
    assert result.stderr == b'csvv: No space left on device\n'


def test_closed_stdin_is_an_error() -> None:
    result = subprocess.run([sys.executable, str(CSVV)], capture_output=True, check=False,
                            preexec_fn=lambda: os.close(0))  # pylint: disable=subprocess-popen-preexec-fn
    assert result.returncode == 1
    assert result.stdout == b''
    assert result.stderr == f'csvv: stdin: {os.strerror(errno.EBADF)}\n'.encode()


def test_closed_stdout_is_an_error(tmp_path) -> None:
    path = tmp_path / 'in.csv'
    path.write_bytes(b'a,b\n')
    result = subprocess.run([sys.executable, str(CSVV), str(path)], stderr=subprocess.PIPE,
                            check=False, preexec_fn=lambda: os.close(1))  # pylint: disable=subprocess-popen-preexec-fn
    assert result.returncode == 1
    assert result.stderr == f'csvv: stdout: {os.strerror(errno.EBADF)}\n'.encode()


def test_interrupt_exits_quietly(csvv: types.ModuleType, monkeypatch) -> None:
    def interrupted(*_args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(csvv, 'process', interrupted)
    monkeypatch.setattr(csvv, 'configure_stdio', lambda: None)
    assert csvv.main([]) == 128 + signal.SIGINT
