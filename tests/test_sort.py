'''Tests for --sort.'''

# A test's name says what it checks.
# pylint: disable=missing-function-docstring

import types

import pytest

from conftest import Run


@pytest.mark.parametrize(('text', 'column', 'numeric', 'reverse'), [
    ('median', 'median', False, False),
    ('median:n', 'median', True, False),
    ('median:r', 'median', False, True),
    ('median:nr', 'median', True, True),
    ('median:rn', 'median', True, True),
    ('2', '2', False, False),
    ('2:n', '2', True, False),
    ('2:4', '2:4', False, False),
    ('2:4:n', '2:4', True, False),
    ('5:2:-1', '5:2:-1', False, False),
    ('5:2:-1:r', '5:2:-1', False, True),
    ('2:', '2:', False, False),
    ('-2:', '-2:', False, False),
    ('2::', '2::', False, False),
    ('2::n', '2:', True, False),
    ('::-1', '::-1', False, False),
    ('a:n:', 'a:n:', False, False),
    ('a:n', 'a', True, False),
    ('a:x', 'a:x', False, False),
    ('n', 'n', False, False),
    ('#3:n', '#3', True, False),
])
def test_key_parsing(csvv: types.ModuleType, text: str, column: str, numeric: bool,
                     reverse: bool) -> None:
    key = csvv.sort_key(text)
    assert (key.column.text, key.numeric, key.reverse) == (column, numeric, reverse)


@pytest.mark.parametrize(('text', 'column', 'reverse'), [
    ('file:v', 'file', False),
    ('file:vr', 'file', True),
    ('file:rv', 'file', True),
    ('2:4:v', '2:4', False),
    ('a:v:', None, False),
])
def test_natural_key_parsing(csvv: types.ModuleType, text: str, column: str | None,
                             reverse: bool) -> None:
    key = csvv.sort_key(text)
    if column is None:
        assert (key.column.text, key.natural) == (text, False)
    else:
        assert (key.column.text, key.numeric, key.natural, key.reverse) == (
            column, False, True, reverse)


def sort(run: Run, *args: str, cells: list[str]) -> list[str]:
    '''Sort one column of cells and return them in their new order.'''
    data = ''.join(f'{c}\n' for c in cells).encode()
    result = run(*args, stdin=data)
    assert result.returncode == 0, result.stderr
    return result.stdout.decode().splitlines()


def test_text_order_is_by_code_point(run: Run) -> None:
    cells = ['b', 'B', 'a', '10', '9', 'é', 'A']
    assert sort(run, '--sort', '1', cells=cells) == ['10', '9', 'A', 'B', 'a', 'b', 'é']


def test_text_reverse(run: Run) -> None:
    assert sort(run, '--sort', '1:r', cells=['b', 'c', 'a']) == ['c', 'b', 'a']


def test_numeric_order(run: Run) -> None:
    cells = ['10', '9', '-1', '1e1', '0.5', 'inf', '-inf']
    assert sort(run, '--sort', '1:n', cells=cells) == [
        '-inf', '-1', '0.5', '9', '10', '1e1', 'inf']


def test_numeric_reverse(run: Run) -> None:
    cells = ['10', '9', '-1', '0.5']
    assert sort(run, '--sort', '1:nr', cells=cells) == ['10', '9', '0.5', '-1']


def test_non_numbers_sort_last_in_text_order(run: Run) -> None:
    cells = ['b', '2', '""', 'nan', '1', 'a', '"1,234"']
    assert sort(run, '--sort', '1:n', cells=cells) == [
        '1', '2', '""', '"1,234"', 'a', 'b', 'nan']


def test_non_numbers_sort_last_when_reversed(run: Run) -> None:
    cells = ['b', '2', 'a', '1']
    assert sort(run, '--sort', '1:nr', cells=cells) == ['2', '1', 'b', 'a']


def test_long_integers_sort_exactly(run: Run) -> None:
    cells = ['9007199254740993', '9007199254740992']
    assert sort(run, '--sort', '1:n', cells=cells) == cells[::-1]


def test_natural_order(run: Run) -> None:
    cells = ['file10', 'file2', 'file1', 'file', 'a', '10', '9']
    assert sort(run, '--sort', '1:v', cells=cells) == [
        '9', '10', 'a', 'file', 'file1', 'file2', 'file10']


def test_natural_order_compares_every_run(run: Run) -> None:
    cells = ['v1.10', 'v1.9', 'v1.2.3', 'v1.2', 'v10.0']
    assert sort(run, '--sort', '1:v', cells=cells) == [
        'v1.2', 'v1.2.3', 'v1.9', 'v1.10', 'v10.0']


def test_natural_reverse(run: Run) -> None:
    cells = ['file2', 'file10', 'file1']
    assert sort(run, '--sort', '1:vr', cells=cells) == ['file10', 'file2', 'file1']


def test_natural_order_breaks_ties_by_leading_zeros(run: Run) -> None:
    cells = ['file2', 'file002', 'file3', 'file02', 'file1']
    assert sort(run, '--sort', '1:v', cells=cells) == [
        'file1', 'file002', 'file02', 'file2', 'file3']
    assert sort(run, '--sort', '1:vr', cells=cells) == [
        'file3', 'file2', 'file02', 'file002', 'file1']


def test_natural_order_takes_only_ascii_digits(run: Run) -> None:
    # Arabic-Indic 2 is text, which sorts after the ASCII digits.
    assert sort(run, '--sort', '1:v', cells=['\u0662', '10']) == ['10', '\u0662']


def test_natural_order_has_no_limit_on_runs(csvv: types.ModuleType) -> None:
    short, long = '9' * 5000, '1' + '0' * 5000
    assert csvv.natural_key(short) < csvv.natural_key(long)


def test_sort_is_stable(run: Run) -> None:
    data = b'1,a\n0,b\n1,c\n0,d\n1,e\n'
    for key in ('1', '1:n'):
        assert run('--sort', key, stdin=data).stdout == b'0,b\n0,d\n1,a\n1,c\n1,e\n'
    assert run('--sort', '1:r', stdin=data).stdout == b'1,a\n1,c\n1,e\n0,b\n0,d\n'


def test_equal_numbers_keep_their_order(run: Run) -> None:
    data = b'1.0,a\n1,b\n01,c\n'
    assert run('--sort', '1:n', stdin=data).stdout == data


def test_first_key_takes_priority(run: Run) -> None:
    data = b'b,2\na,2\nb,1\na,1\n'
    result = run('--sort', '2:n', '--sort', '1', stdin=data)
    assert result.stdout == b'a,1\nb,1\na,2\nb,2\n'


def test_keys_mix_directions(run: Run) -> None:
    data = b'b,2\na,2\nb,1\na,1\n'
    result = run('--sort', '1:r', '--sort', '2:n', stdin=data)
    assert result.stdout == b'b,1\nb,2\na,1\na,2\n'


def test_slice_is_one_key_per_column(run: Run) -> None:
    data = b'x,2,b\ny,1,b\nz,1,a\n'
    assert run('--sort', '2:3', stdin=data).stdout == b'z,1,a\ny,1,b\nx,2,b\n'
    assert run('--sort', '2:3:r', stdin=data).stdout == b'x,2,b\ny,1,b\nz,1,a\n'
    assert run('--sort', '3:2:-1', stdin=data).stdout == b'z,1,a\ny,1,b\nx,2,b\n'


def test_slice_is_clamped(run: Run) -> None:
    data = b'b,1\na,2\n'
    assert run('--sort', '2:9:n', stdin=data).stdout == b'b,1\na,2\n'


def test_open_slice(run: Run) -> None:
    data = b'x,1,b\ny,1,a\nz,0,c\n'
    for key in ('2:', '2::', '#2:'):
        assert run('--sort', key, stdin=data).stdout == b'z,0,c\ny,1,a\nx,1,b\n'
    assert run('--sort=-2:', stdin=data).stdout == b'z,0,c\ny,1,a\nx,1,b\n'


def test_header_stays_on_top(run: Run) -> None:
    result = run('-H', '--sort', 'v:n', stdin=b'k,v\na,3\nb,1\nc,2\n')
    assert result.stdout == b'k,v\nb,1\nc,2\na,3\n'


def test_name_ending_in_flag_letters_needs_a_position(run: Run) -> None:
    data = b'a:n,x\n2,a\n10,b\n'
    result = run('-H', '--sort', 'a:n', stdin=data)
    assert result.returncode == 1
    assert b"no column named 'a'" in result.stderr
    assert run('-H', '--sort', '1', stdin=data).stdout == b'a:n,x\n10,b\n2,a\n'


def test_name_wins_over_position(run: Run) -> None:
    result = run('-H', '--sort', '2', stdin=b'2,x\nb,1\na,2\n')
    assert result.stdout == b'2,x\na,2\nb,1\n'


def test_negative_position(run: Run) -> None:
    result = run('--sort=-1:n', stdin=b'a,10\nb,9\n')
    assert result.stdout == b'b,9\na,10\n'


def test_quoted_values_survive(run: Run) -> None:
    data = b'"b,1",2\n"a\nx",1\n'
    assert run('--sort', '1', stdin=data).stdout == b'"a\nx",1\n"b,1",2\n'


def test_filter_sort_select(run: Run) -> None:
    data = b'name,err,median\nalpha,0,0.025\nbeta,99,0.031\ngamma,7,0.010\ndelta,3,x\n'
    result = run('--select', 'name', '--sort', 'median:nr', '-e', 'err<50', '-H', stdin=data)
    assert result.stdout == b'name\nalpha\ngamma\ndelta\n'


def test_sort_empty_input(run: Run) -> None:
    for args in (('--sort', '1'), ('-H', '--sort', 'a')):
        result = run(*args, stdin=b'')
        assert (result.returncode, result.stdout) == (0, b'')


def test_sort_header_only(run: Run) -> None:
    assert run('-H', '--sort', 'a', stdin=b'a,b\n').stdout == b'a,b\n'


def test_ragged_row_stops_the_sort_before_any_output(run: Run) -> None:
    result = run('--sort', '1', stdin=b'b,1\na\n')
    assert (result.returncode, result.stdout) == (1, b'')
    assert b'record 2, line 2' in result.stderr


@pytest.mark.parametrize(('key', 'message'), [
    (':n', b'has no column'),
    ('#x', b'"#" must be followed by a position'),
    ('#0:n', b'numbered from 1'),
    ('a:nv', b'has both n and v'),
])
def test_bad_key_is_a_usage_error(run: Run, key: str, message: bytes) -> None:
    result = run('-H', '--sort', key, stdin=b'a\n')
    assert result.returncode == 2
    assert message in result.stderr


def test_name_without_header_is_a_usage_error(run: Run) -> None:
    result = run('--sort', 'a:n', stdin=b'a\n')
    assert result.returncode == 2
    assert b"'a' is a column name, which needs -H" in result.stderr


@pytest.mark.parametrize(('key', 'message'), [
    ('nope', b"no column named 'nope'"),
    ('#5', b'out of range, since the input has 2 columns'),
    ('#7:9', b'out of range'),
])
def test_bad_column_is_a_data_error(run: Run, key: str, message: bytes) -> None:
    result = run('-H', '--sort', key, stdin=b'a,b\n1,2\n')
    assert (result.returncode, result.stdout) == (1, b'')
    assert message in result.stderr


@pytest.mark.parametrize('args', [
    ('-e', '2>5', '--sort', '9'),
    ('-e', '2>5', '--select', '1', '-e', '#9<1'),
])
def test_column_errors_do_not_depend_on_the_data(run: Run, args: tuple[str, ...]) -> None:
    # The filter drops every row, so no row ever reaches the bad column.
    for data in (b'a,1\n', b'a,9\n'):
        result = run(*args, stdin=data)
        assert result.returncode == 1
        assert b'out of range' in result.stderr
