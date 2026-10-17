'''Tests for -e and the rule for what counts as a number.'''

# A test's name says what it checks.
# pylint: disable=missing-function-docstring

import types

import pytest

from conftest import Run


@pytest.mark.parametrize(('text', 'expected'), [
    ('99', 99),
    ('-7', -7),
    ('099', 99),
    (' 5 ', 5),
    ('1_000', 1000),
    ('99.0', 99.0),
    ('1e5', 100000.0),
    ('.5', 0.5),
    ('inf', float('inf')),
    ('-Infinity', float('-inf')),
    ('9007199254740993', 9007199254740993),
])
def test_numbers(csvv: types.ModuleType, text: str, expected: float) -> None:
    n = csvv.to_number(text)
    assert n == expected
    assert type(n) is type(expected)


@pytest.mark.parametrize('text', ['', ' ', 'nan', 'NaN', '-nan', '1,234', '0x1F', '1.2.3',
                                  'five', '1 2', '½'])
def test_not_numbers(csvv: types.ModuleType, text: str) -> None:
    assert csvv.to_number(text) is None


def test_long_integers_compare_exactly(csvv: types.ModuleType) -> None:
    assert csvv.to_number('9007199254740993') != csvv.to_number('9007199254740992')


@pytest.mark.parametrize(('text', 'column', 'op', 'value'), [
    ('a==1', 'a', '==', '1'),
    ('a<=1', 'a', '<=', '1'),
    ('a<1', 'a', '<', '1'),
    ('a!~x', 'a', '!~', 'x'),
    ('a~x', 'a', '~', 'x'),
    (' a  >=  1 ', 'a', '>=', '1'),
    ('a~x==y', 'a', '~', 'x==y'),
    ('a==', 'a', '==', ''),
    ('a b<3', 'a b', '<', '3'),
    ('wow!<3', 'wow!', '<', '3'),
    ('#2>3', '#2', '>', '3'),
    ('a=b==c', 'a=b', '==', 'c'),
])
def test_condition_parsing(csvv: types.ModuleType, text: str, column: str, op: str,
                           value: str) -> None:
    c = csvv.condition(text)
    assert (c.column.text, c.op, c.value) == (column, op, value)


@pytest.mark.parametrize(('op', 'value', 'cells'), [
    ('==', '99', ['99', '99.0', '099', '9.9e1', ' 99']),
    ('!=', '99', ['98', 'x', '']),
    ('<', '0.03', ['0.02', '-1', '2e-2']),
    ('<=', '5', ['5', '4.99', '-inf']),
    ('>', '9', ['10', '1e3', 'inf']),
    ('>=', '10', ['10', '10.0', '11']),
    ('==', 'abc', ['abc']),
    ('!=', 'abc', ['ABC', 'abcd', '']),
    ('<', 'm', ['a', 'B', 'Z', 'lzz']),
    ('>', 'Z', ['a', 'é']),
    ('~', '^a.c$', ['abc', 'a-c']),
    ('~', 'b', ['abc', 'b']),
    ('~', '(?i)^a', ['abc', 'ABC']),
    ('!~', '^a', ['ba', '', 'A']),
    ('==', '', ['']),
    ('~', '', ['', 'x']),
])
def test_matches(csvv: types.ModuleType, op: str, value: str, cells: list[str]) -> None:
    c = csvv.condition(f'x{op}{value}')
    for cell in cells:
        assert c.matches(cell), cell


@pytest.mark.parametrize(('op', 'value', 'cells'), [
    ('==', '99', ['98', 'x', '', '99x', 'nan']),
    ('!=', '99', ['99', '99.0', '099']),
    ('<', '0.03', ['0.03', '1', 'x', '']),
    ('>', '9', ['9', '-10', 'x', 'nan']),
    ('==', 'abc', ['ABC', ' abc']),
    ('<', 'm', ['m', 'z', 'é']),
    ('~', '^a', ['ba', '']),
    ('~', '(?i)^a', ['ba']),
    ('!~', 'b', ['abc']),
])
def test_does_not_match(csvv: types.ModuleType, op: str, value: str,
                        cells: list[str]) -> None:
    c = csvv.condition(f'x{op}{value}')
    for cell in cells:
        assert not c.matches(cell), cell


DATA = b'name,err,median\nalpha,0,0.025\nbeta,99,0.031\ngamma,099,x\ndelta,7,0.010\n'


def test_numeric_filter(run: Run) -> None:
    result = run('-H', '-e', 'median<0.03', stdin=DATA)
    assert result.stdout == b'name,err,median\nalpha,0,0.025\ndelta,7,0.010\n'


def test_numeric_equality_matches_other_spellings(run: Run) -> None:
    result = run('-H', '-e', 'err==99', stdin=DATA)
    assert result.stdout == b'name,err,median\nbeta,99,0.031\ngamma,099,x\n'


def test_exact_text_with_a_regex(run: Run) -> None:
    result = run('-H', '-e', 'err~^099$', stdin=DATA)
    assert result.stdout == b'name,err,median\ngamma,099,x\n'


def test_not_equal_keeps_non_numbers(run: Run) -> None:
    result = run('-H', '-e', 'median!=0.025', '--select', 'name', stdin=DATA)
    assert result.stdout == b'name\nbeta\ngamma\ndelta\n'


def test_every_filter_must_match(run: Run) -> None:
    result = run('-H', '-e', 'median<0.03', '-e', 'name~^[ab]', '--select', 'name',
                 stdin=DATA)
    assert result.stdout == b'name\nalpha\n'


def test_filter_on_a_column_that_select_drops(run: Run) -> None:
    result = run('--select', '1', '-e', '#2>5', stdin=DATA[DATA.index(b'\n') + 1:])
    assert result.stdout == b'beta\ngamma\ndelta\n'


def test_filter_by_position_without_header(run: Run) -> None:
    result = run('-e', '2==0', stdin=b'a,0\nb,1\n')
    assert result.stdout == b'a,0\n'


def test_header_kept_when_nothing_matches(run: Run) -> None:
    result = run('-H', '-e', 'err>1000', stdin=DATA)
    assert (result.returncode, result.stdout) == (0, b'name,err,median\n')


def test_name_wins_over_position(run: Run) -> None:
    result = run('-H', '-e', '1==b', stdin=b'x,1\na,b\nb,a\n')
    assert result.stdout == b'x,1\na,b\n'


def test_filter_value_starting_with_a_dash(run: Run) -> None:
    result = run('-e=#1<-1', stdin=b'-5\n0\n')
    assert result.stdout == b'-5\n'


def test_filter_on_empty_input(run: Run) -> None:
    for args in (('-e', '1==a'), ('-H', '-e', 'a==1')):
        result = run(*args, stdin=b'')
        assert (result.returncode, result.stdout) == (0, b'')


@pytest.mark.parametrize(('expr', 'message'), [
    ('abc', b'has no operator'),
    ('==1', b'has no column'),
    ('a~(', b'invalid regex'),
    ('#x<1', b'"#" must be followed by a position'),
    ('#1:2<1', b'is a slice'),
    ('#0<1', b'numbered from 1'),
])
def test_bad_filter_is_a_usage_error(run: Run, expr: str, message: bytes) -> None:
    result = run('-H', '-e', expr, stdin=DATA)
    assert result.returncode == 2
    assert message in result.stderr


@pytest.mark.parametrize(('expr', 'message'), [
    ('name==a', b"'name' is a column name, which needs -H"),
    ('1:2<1', b'is a slice'),
    ('0<1', b'numbered from 1'),
])
def test_bad_filter_without_header_is_a_usage_error(run: Run, expr: str,
                                                    message: bytes) -> None:
    result = run('-e', expr, stdin=DATA)
    assert result.returncode == 2
    assert message in result.stderr


@pytest.mark.parametrize(('expr', 'message'), [
    ('nope<1', b"no column named 'nope'"),
    ('1:2<1', b'is a slice'),
    ('#9<1', b'out of range, since the input has 3 columns'),
    ('-9<1', b'out of range'),
])
def test_bad_filter_column_is_a_data_error(run: Run, expr: str, message: bytes) -> None:
    result = run('-H', '-e', expr, stdin=DATA)
    assert (result.returncode, result.stdout) == (1, b'')
    assert message in result.stderr


def test_out_of_range_without_header(run: Run) -> None:
    result = run('-e', '9<1', stdin=b'a,b\n')
    assert result.returncode == 1
    assert b'out of range' in result.stderr
