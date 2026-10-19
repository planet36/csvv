'''Tests for --select and the rules for naming columns.'''

# A test's name says what it checks.
# pylint: disable=missing-function-docstring

import types

import pytest

from conftest import Run


def positions(csvv: types.ModuleType, text: str, width: int = 6,
              names: tuple[str, ...] | None = None) -> list[int]:
    '''Return the 1-based positions that the column list text names.'''
    header = None if names is None else csvv.Header(names)
    return [i + 1 for i in csvv.resolve(csvv.column_list(text), header, width)]


@pytest.mark.parametrize(('text', 'expected'), [
    ('3', [3]),
    ('-1', [6]),
    ('-6', [1]),
    ('#2', [2]),
    ('#-2', [5]),
    ('2:4', [2, 3, 4]),
    ('5:2:-1', [5, 4, 3, 2]),
    ('4:', [4, 5, 6]),
    (':2', [1, 2]),
    ('-2:', [5, 6]),
    ('::-1', [6, 5, 4, 3, 2, 1]),
    ('::2', [1, 3, 5]),
    ('1,5:', [1, 5, 6]),
    ('2:2', [2]),
    ('-1:-1', [6]),
    (':-2', [1, 2, 3, 4, 5]),
    ('-2::-1', [5, 4, 3, 2, 1]),
    (':1:-1', [6, 5, 4, 3, 2, 1]),
    ('4:2', []),
    ('2:4:-1', []),
    ('1,1', [1, 1]),
    ('#2:4', [2, 3, 4]),
])
def test_positions_and_slices(csvv: types.ModuleType, text: str, expected: list[int]) -> None:
    assert positions(csvv, text) == expected


@pytest.mark.parametrize(('text', 'expected'), [
    pytest.param('7', [], id='index past the end'),
    pytest.param('-7', [], id='index before the start'),
    pytest.param('2,9,3', [2, 3], id='ignored in a list'),
    pytest.param('5:9', [5, 6], id='slice past the end'),
    pytest.param('-9:2', [1, 2], id='slice before the start'),
    pytest.param('9:', [], id='slice wholly past the end'),
    pytest.param('9::-1', [6, 5, 4, 3, 2, 1], id='reversed slice clamped'),
    pytest.param('2:-9:-1', [2, 1], id='reversed slice past the start'),
])
def test_out_of_range(csvv: types.ModuleType, text: str, expected: list[int]) -> None:
    assert positions(csvv, text) == expected


@pytest.mark.parametrize('text', ['0', '0:3', '1:0', '0:3:0'])
def test_zero_is_an_error(csvv: types.ModuleType, text: str) -> None:
    with pytest.raises(csvv.DataError, match='numbered from 1'):
        positions(csvv, text)


@pytest.mark.parametrize('text', ['::0', '1:3:0'])
def test_zero_step_is_an_error(csvv: types.ModuleType, text: str) -> None:
    with pytest.raises(csvv.DataError, match='step of 0'):
        positions(csvv, text)


@pytest.mark.parametrize('text', ['#0', '#1:0'])
def test_forced_zero_is_caught_while_parsing(csvv: types.ModuleType, text: str) -> None:
    with pytest.raises(csvv.argparse.ArgumentTypeError, match='numbered from 1'):
        csvv.column_list(text)


def test_name_wins_over_position(csvv: types.ModuleType) -> None:
    names = ('a', '3', 'b', 'c')
    assert positions(csvv, '3', 4, names) == [2]
    assert positions(csvv, '#3', 4, names) == [3]
    assert positions(csvv, '2', 4, names) == [2]


def test_name_that_looks_like_a_slice(csvv: types.ModuleType) -> None:
    assert positions(csvv, '1:2', 3, ('x', '1:2', 'y')) == [2]
    assert positions(csvv, '2:3', 3, ('x', '1:2', 'y')) == [2, 3]


def test_names_match_exactly(csvv: types.ModuleType) -> None:
    with pytest.raises(csvv.DataError, match="no column named 'A'"):
        positions(csvv, 'A', 2, ('a', 'b'))
    with pytest.raises(csvv.DataError, match="no column named ' a'"):
        positions(csvv, ' a', 2, ('a', 'b'))


def test_duplicate_name_is_ambiguous(csvv: types.ModuleType) -> None:
    with pytest.raises(csvv.DataError, match='columns 1 and 3 both have it'):
        positions(csvv, 'x', 3, ('x', 'y', 'x'))
    with pytest.raises(csvv.DataError, match='columns 1, 2, and 4 all have it'):
        positions(csvv, 'x', 4, ('x', 'x', 'y', 'x'))
    assert positions(csvv, '#3', 3, ('x', 'y', 'x')) == [3]


def test_select_by_name(run: Run) -> None:
    result = run('-H', '--select', 'c,a', stdin=b'a,b,c\n1,2,3\n')
    assert (result.returncode, result.stdout) == (0, b'c,a\n3,1\n')


def test_select_by_position(run: Run) -> None:
    result = run('--select', '3,1', stdin=b'a,b,c\n1,2,3\n')
    assert result.stdout == b'c,a\n3,1\n'


def test_select_negative_needs_equals(run: Run) -> None:
    assert run('--select=-1', stdin=b'a,b\n1,2\n').stdout == b'b\n2\n'
    assert run('--select=-2:', stdin=b'a,b,c\n').stdout == b'b,c\n'


def test_select_repeated_lists_join(run: Run) -> None:
    result = run('--select', '3', '--select', '1:2', stdin=b'a,b,c\n')
    assert result.stdout == b'c,a,b\n'


def test_select_keeps_quoted_values(run: Run) -> None:
    result = run('--select', '2', stdin=b'a,"x,y"\n1,"line\nbreak"\n')
    assert result.stdout == b'"x,y"\n"line\nbreak"\n'


def test_select_header_only(run: Run) -> None:
    result = run('-H', '--select', 'b', stdin=b'a,b\n')
    assert (result.returncode, result.stdout) == (0, b'b\n')


def test_select_empty_input(run: Run) -> None:
    for args in (('--select', '1'), ('-H', '--select', 'b')):
        result = run(*args, stdin=b'')
        assert (result.returncode, result.stdout) == (0, b'')


def test_select_after_ragged_pad(run: Run) -> None:
    result = run('--ragged', 'pad', '--select=-1', stdin=b'a,b,c\n1\n')
    assert result.stdout == b'c\n""\n'


def test_name_without_header_is_a_usage_error(run: Run) -> None:
    result = run('--select', 'b', stdin=b'a,b\n')
    assert result.returncode == 2
    assert b"'b' is a column name, which needs -H" in result.stderr


def test_unknown_name_is_a_data_error(run: Run) -> None:
    result = run('-H', '--select', 'nope', stdin=b'a,b\n1,2\n')
    assert (result.returncode, result.stdout) == (1, b'')
    assert result.stderr == b"csvv: no column named 'nope'\n"


@pytest.mark.parametrize(('args', 'message'), [
    pytest.param(('--select', '5'), b"'5' is out of range", id='one item'),
    pytest.param(('--select', '5,7:9'), b"'5' and '7:9' are out of range", id='two items'),
    pytest.param(('--select', '5', '--select', '#-9,6'),
                 b"'5', '#-9', and '6' are out of range", id='three items'),
    pytest.param(('-H', '--select', '5'), b"'5' is out of range", id='with a header'),
])
def test_selecting_no_columns_is_a_data_error(run: Run, args: tuple[str, ...],
                                              message: bytes) -> None:
    result = run(*args, stdin=b'a,b\n1,2\n')
    assert (result.returncode, result.stdout) == (1, b'')
    assert result.stderr == (b'csvv: --select chose no columns, since ' + message +
                             b' and the input has 2 columns\n')


def test_ambiguous_name_is_a_data_error(run: Run) -> None:
    result = run('-H', '--select', 'x', stdin=b'x,x\n1,2\n')
    assert result.returncode == 1
    assert b'ambiguous' in result.stderr


@pytest.mark.parametrize('text', ['a,,b', ',', '#x', '#', '#0', '#1:0'])
def test_bad_list_is_a_usage_error(run: Run, text: str) -> None:
    result = run('-H', '--select', text, stdin=b'a,b\n')
    assert result.returncode == 2
    assert b'argument --select' in result.stderr


def test_zero_with_header_and_no_such_name(run: Run) -> None:
    result = run('-H', '--select', '0', stdin=b'a,b\n')
    assert result.returncode == 1
    assert b'columns are numbered from 1' in result.stderr


def test_zero_with_header_and_such_a_name(run: Run) -> None:
    result = run('-H', '--select', '0', stdin=b'0,b\n1,2\n')
    assert result.stdout == b'0\n1\n'


BENCH = b'command,time_mean,time_median,user,time_max\nsleep 1,1.0,1.0,0.0,1.1\n'


def header_of(run: Run, *args: str, data: bytes = BENCH) -> bytes:
    '''Run csvv with -H and return the header line it writes.'''
    result = run('-H', *args, stdin=data)
    assert result.returncode == 0, result.stderr
    return result.stdout.split(b'\n')[0]


def test_regex_selects_matching_columns_in_header_order(run: Run) -> None:
    assert header_of(run, '--select-regex', '^time_') == b'time_mean,time_median,time_max'
    assert header_of(run, '--select-regex', 'max|mean') == b'time_mean,time_max'


def test_regex_selects_the_rows_too(run: Run) -> None:
    result = run('-H', '--select-regex', '_me', stdin=BENCH)
    assert result.stdout == b'time_mean,time_median\n1.0,1.0\n'


def test_regex_can_ignore_case(run: Run) -> None:
    assert header_of(run, '--select-regex', '(?i)^USER$') == b'user'


def test_regex_may_hold_a_comma(run: Run) -> None:
    assert header_of(run, '--select-regex', '^time_m.{2,3}$') == b'time_mean,time_max'


@pytest.mark.parametrize(('args', 'expected'), [
    (('--select', 'command', '--select-regex', '^time_m'),
     b'command,time_mean,time_median,time_max'),
    (('--select-regex', '^time_m', '--select', 'command'),
     b'time_mean,time_median,time_max,command'),
    (('--select-regex', 'max', '--select', 'user', '--select-regex', 'mean'),
     b'time_max,user,time_mean'),
    (('--select', '1', '--select-regex', 'user', '--select', '-1'),
     b'command,user,time_max'),
])
def test_regex_joins_select_in_the_order_given(run: Run, args: tuple[str, ...],
                                               expected: bytes) -> None:
    assert header_of(run, *args) == expected


def test_regex_can_repeat_a_column(run: Run) -> None:
    assert header_of(run, '--select', 'command', '--select-regex', 'mand') == b'command,command'


def test_regex_with_header_only(run: Run) -> None:
    result = run('-H', '--select-regex', 'user', stdin=b'command,user\n')
    assert (result.returncode, result.stdout) == (0, b'user\n')


def test_regex_with_empty_input(run: Run) -> None:
    result = run('-H', '--select-regex', 'x', stdin=b'')
    assert (result.returncode, result.stdout) == (0, b'')


def test_regex_without_header_is_a_usage_error(run: Run) -> None:
    result = run('--select-regex', 'user', stdin=BENCH)
    assert result.returncode == 2
    assert b"argument --select-regex: 'user' matches column names, which needs -H" in result.stderr


def test_invalid_regex_is_a_usage_error(run: Run) -> None:
    result = run('-H', '--select-regex', '(', stdin=BENCH)
    assert result.returncode == 2
    assert b"'(': invalid regex" in result.stderr


def test_regex_that_matches_nothing_is_a_data_error(run: Run) -> None:
    result = run('-H', '--select-regex', 'nope', stdin=BENCH)
    assert (result.returncode, result.stdout) == (1, b'')
    assert result.stderr == b"csvv: no column name matches the regex 'nope'\n"
