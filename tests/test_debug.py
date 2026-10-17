'''Tests for --debug.'''

# A test's name says what it checks.
# pylint: disable=missing-function-docstring

import pytest

from conftest import Run

DATA = b'name,err,median\nalpha,0,0.025\nbeta,99,0.031\ngamma,7,x\ndelta,3,\n'


def debug_lines(run: Run, *args: str, stdin: bytes = DATA) -> list[str]:
    '''Run csvv with --debug and return its stderr lines.'''
    result = run('--debug', *args, stdin=stdin)
    assert result.returncode == 0, result.stderr
    return result.stderr.decode().splitlines()


@pytest.mark.parametrize('args', [
    (),
    ('-H',),
    ('-H', '-e', 'median<0.03', '--sort', 'median:nr', '--select', 'name,9,3'),
    ('--sort', '2:n', '--select=-1'),
])
def test_output_is_unchanged(run: Run, args: tuple[str, ...]) -> None:
    plain = run(*args, stdin=DATA)
    debug = run('--debug', *args, stdin=DATA)
    assert debug.stdout == plain.stdout
    assert debug.returncode == plain.returncode
    assert plain.stderr == b''


def test_filter_notes(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', 'median<0.03', '-e', 'name~^a', '-e', 'name==beta')
    assert "csvv: -e 'median<0.03': column 3 ('median') < 0.03, comparing numbers" in lines
    assert "csvv: -e 'name~^a': column 1 ('name') ~ '^a', a regex search" in lines
    assert "csvv: -e 'name==beta': column 1 ('name') == 'beta', comparing text" in lines


def test_filter_notes_for_a_slice(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', '2:3>0', '-e', '::!~x', '-e', 'err!=1')
    assert ("csvv: -e '2:3>0': any of columns 2 ('err'), 3 ('median') > 0, "
            'comparing numbers') in lines
    assert ("csvv: -e '::!~x': none of columns 1 ('name'), 2 ('err'), 3 ('median') ~ 'x', "
            'a regex search') in lines
    assert "csvv: -e 'err!=1': column 2 ('err') != 1, comparing numbers" in lines


def test_warns_about_non_numbers_in_each_column_of_a_slice(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', '2:3>0')
    warnings = [line for line in lines if 'warning' in line]
    assert warnings == [("csvv: warning: -e '2:3>0' met 2 cells that are not numbers, "
                         'which failed the comparison')]


def test_sort_notes(run: Run) -> None:
    lines = debug_lines(run, '-H', '--sort', 'median:nr', '--sort', '1:2', '--sort', 'name:v',
                        '--sort', 'name:vir')
    assert "csvv: --sort 'median:nr': column 3 ('median'), as numbers, reversed" in lines
    assert "csvv: --sort '1:2': columns 1 ('name'), 2 ('err'), as text" in lines
    assert "csvv: --sort 'name:v': column 1 ('name'), as text in natural order" in lines
    assert ("csvv: --sort 'name:vir': column 1 ('name'), as text in natural order, "
            'ignoring case, reversed') in lines
    assert 'csvv: sorting holds every row in memory' in lines


def test_select_notes_without_header(run: Run) -> None:
    lines = debug_lines(run, '--select', '3,1:2')
    assert "csvv: --select '3': column 3" in lines
    assert "csvv: --select '1:2': columns 1, 2" in lines


def test_counts(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', 'err<50')
    assert lines[-1] == ('csvv: rows read: 4, kept by the filter: 3, written: 3 '
                         '(not counting the header)')


def test_counts_without_header_or_filter(run: Run) -> None:
    assert debug_lines(run)[-1] == 'csvv: rows read: 5, written: 5'


def test_counts_on_empty_input(run: Run) -> None:
    assert debug_lines(run, '-H', '--sort', 'a', stdin=b'') == [
        'csvv: rows read: 0, written: 0']


def test_warns_when_a_number_matches_a_name(run: Run) -> None:
    data = b'x,3\na,b\n'
    for option in ('--select', '--sort'):
        lines = debug_lines(run, '-H', option, '3', stdin=data)
        assert (f"csvv: warning: {option} '3' matched the column named '3', "
                'so write "#3" to mean the position') in lines
        assert not any('warning' in line
                       for line in debug_lines(run, '-H', option, '#2', stdin=data))
    lines = debug_lines(run, '-H', '-e', '3==b', stdin=data)
    assert any("warning: -e '3==b' matched the column named '3'" in line for line in lines)


def test_no_warning_for_a_name_that_is_not_a_number(run: Run) -> None:
    lines = debug_lines(run, '-H', '--select', 'name')
    assert not any('warning' in line for line in lines)


def test_warns_about_an_ignored_position(run: Run) -> None:
    lines = debug_lines(run, '--select', '1,9,7:8')
    assert "csvv: warning: --select '9' was ignored, since the input has 3 columns" in lines
    assert "csvv: warning: --select '7:8' was ignored, since the input has 3 columns" in lines


def test_warns_about_non_numbers_in_a_filter(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', 'median<0.03')
    assert ("csvv: warning: -e 'median<0.03' met 2 cells that are not numbers, "
            'which failed the comparison') in lines


def test_warns_that_non_numbers_pass_not_equal(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', 'median!=0.03')
    assert ("csvv: warning: -e 'median!=0.03' met 2 cells that are not numbers, "
            'which counted as unequal') in lines


def test_warns_about_non_numbers_in_a_sort(run: Run) -> None:
    lines = debug_lines(run, '-H', '--sort', 'median:n')
    assert ("csvv: warning: --sort 'median:n' met 2 cells that are not numbers, "
            'which sorted after the numbers') in lines


def test_counts_one_non_number(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', 'median<0.03', stdin=DATA[:DATA.rindex(b'delta')])
    assert any('met 1 cell that is not a number' in line for line in lines)


def test_no_non_number_warning_for_text_or_regex(run: Run) -> None:
    lines = debug_lines(run, '-H', '-e', 'median!=x', '-e', 'median~.', '--sort', 'median')
    assert not any('warning' in line for line in lines)


def test_errors_still_reported(run: Run) -> None:
    result = run('--debug', '-H', '--select', 'nope', stdin=DATA)
    assert result.returncode == 1
    assert result.stderr.decode().splitlines()[-1] == "csvv: no column named 'nope'"
