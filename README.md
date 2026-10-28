# csvv

Filter and sort the rows of a CSV file, and select its columns, in one dependency-free Python script.

csvv does a little of what `awk`, `sort`, and `cut` do, but it understands CSV.  A quoted field may hold commas, quotes, and line breaks, and csvv still reads it as one field.  With a header, columns can be named instead of counted.  Every value is written back exactly as it was read.

## Example

Here is `bench.csv`:

```
command,mean,median,runs
sha256sum big.iso,0.412,0.405,10
b2sum big.iso,0.298,0.301,10
md5sum big.iso,0.351,0.349,10
cksum big.iso,0.187,0.190,10
"xxhsum -H128 big.iso",0.061,0.060,10
```

This command keeps the rows whose median is under 0.35, sorts them from slowest to fastest, and prints two columns:

```
$ csvv -H -e 'median<0.35' --sort median:nr --select command,median bench.csv
command,median
md5sum big.iso,0.349
b2sum big.iso,0.301
cksum big.iso,0.190
xxhsum -H128 big.iso,0.060
```

csvv always filters first, then sorts, then selects, whatever order the options are in.  The filter and the sort can therefore use columns that the selection drops.

## Installation

csvv needs Python 3.12 or later, and nothing else.  It has been tested only with Python 3.14.  Copy the script somewhere on your `PATH`:

```sh
install -m 755 csvv ~/.local/bin/
```

To build the man page, which needs [help2man](https://www.gnu.org/software/help2man/), run `make man` and install `csvv.1`:

```sh
make man
install -m 644 csvv.1 ~/.local/share/man/man1/
```

## Usage

```
csvv [OPTION]... [FILE]
```

csvv reads FILE, or stdin when FILE is absent or `-`, and writes CSV to stdout.

| option | meaning |
| --- | --- |
| `-H, --header` | the first record holds column names |
| `-F, --delimiter CHAR` | the input field separator (default `,`) |
| `-o, --output-delimiter CHAR` | the output field separator (default: as `-F`) |
| `--ragged MODE` | handle a record whose length differs from the first: `error` (the default), `pad` a short one with empty fields, or `truncate` a long one |
| `-e, --filter EXPR` | keep only rows matching EXPR (repeatable) |
| `--sort KEY` | sort rows by KEY (repeatable) |
| `--select LIST` | output the columns in LIST, in that order (repeatable) |
| `--select-regex REGEX` | output the columns whose names match REGEX (repeatable) |
| `--debug` | print diagnostics and warnings to stderr |
| `-h, --help` | show the help and exit |
| `-V, --version` | show the version, license, and author, and exit |

CHAR is one character, or `\t` for a tab.  It may not be `"` or a line break, and a tab separator still honors CSV quoting.  `csvv --help` and `man csvv` give the full details.

### Naming columns

A column is named by its position, by a slice, or with `-H` by its name in the header.

- **Positions start at 1**, as in `cut` and `awk`, and negative ones count from the end, so `-1` is the last column.
- **A slice is `START:STOP:STEP`**, as in Python, except that STOP is included, as in `cut -f2-4`.  So `2:4` is columns 2, 3, and 4, `4:` runs from column 4 to the end, and `::-1` is every column in reverse.
- **With `-H`, an exact column name wins over a position.**  A `#` prefix forces a position, so `#3` always means the third column, even when the header has a column named `3`.
- **A position out of range is ignored in `--select`**, but it is an error when `--select` chooses no column at all.  In `-e` and `--sort`, a column out of range is an error.
- **A name that occurs twice in the header is an error**, never a silent pick.  Name such a column by position.
- **0 is never a position**, so `0`, or a slice with an endpoint or step of 0, is an error.

Join a value that starts with `-` to its option with `=`, as in `--select=-2:`, and likewise for `-e`, `--sort`, and `--select-regex`.  Otherwise argparse may read it as an option.

`--select-regex REGEX` selects every column whose name REGEX is found in, in header order.  It needs `-H`, and a regex that matches no column name is an error, as an unknown name is.  It joins `--select` in the order the options are given, so a pattern can pick out columns whose exact names differ from file to file:

```
$ csvv -H --select command --select-regex '^m' bench.csv
command,mean,median
sha256sum big.iso,0.412,0.405
b2sum big.iso,0.298,0.301
md5sum big.iso,0.351,0.349
cksum big.iso,0.187,0.190
xxhsum -H128 big.iso,0.061,0.060
```

The whole value is one regex, so it may hold a comma.  A column picked by both options is output twice, as `--select 1,1` outputs column 1 twice.

### Filtering

`-e` takes `COL OP VALUE`, where COL is a column or a slice of columns, and OP is one of `==`, `!=`, `<`, `<=`, `>`, `>=`, `~`, or `!~`.  A row must match every `-e`.

- **`~` and `!~`** test whether the regex VALUE is found anywhere in the cell.  Start the regex with `(?i)` to ignore case, as in `name~(?i)^b`.
- **The other operators compare numbers when VALUE is a number**, and text otherwise.  So `err==99` matches `99`, `99.0`, and `099`.  For an exact text match, use a regex, as in `id~^007$`.
- **In a numeric test, a cell that is not a number** is never equal, less, or greater, so it passes only `!=`.
- **With a slice, a row passes when any of its columns does.**  So `-e '::~error'` keeps the rows with `error` in any column.  Unlike `grep`, it respects CSV quoting and never tests the header.  For "all of the columns", give one `-e` per column.
- **`!=` and `!~` pass a row only when none of its columns has `==` or `~`**, so they stay the exact opposites of `==` and `~`.  `-e '::!~error'` keeps the rows with no `error` anywhere, like `grep -v`.

The expression is parsed by a small fixed grammar, never evaluated as code.

```
$ csvv -H -e 'command~^(md5|sha)' --select 1,3 bench.csv
command,median
sha256sum big.iso,0.405
md5sum big.iso,0.349
```

### Sorting

`--sort` takes `COL[:FLAGS]`, where FLAGS holds `n` to compare numbers or `v` for natural order, `i` to ignore case, and `r` to reverse, as in `median:nr`.  Text after the last `:` is FLAGS only if it holds nothing but `i`, `n`, `r`, and `v`, so `2:` is a slice.  `n` and `v` together are an error.

- **The sort is stable**, and the first `--sort` takes priority over the next.
- **A slice stands for one key per column**, so `--sort 2:4:n` sorts by column 2, then 3, then 4, all as numbers.
- **In a numeric key, cells that are not numbers sort after the numbers**, in either direction.
- **In natural order, a run of digits compares as a number**, so `file2` sorts before `file10`, and `v1.9` before `v1.10`.  Runs of equal value compare as written, so `file02` sorts before `file2`.  The letter follows `sort -V`, whose version order is similar but not identical.
- **With `i`, text compares without case**, after `str.casefold()`.  Text that differs only in case then compares as written, so `A` sorts just before `a`.  In a numeric key, `i` applies to the cells that are not numbers, so `N/A` and `n/a` sort together.  Leading and trailing whitespace still counts.
- **Text compares by code point**, like `LC_ALL=C sort`.

Sorting holds every row in memory.  Without `--sort`, csvv streams its input and runs in constant memory.

### Viewing as a table

csvv has no table view of its own, because `column` already does that well.  Ask csvv for tab-separated output, which `column` can split safely:

```
$ csvv -H -o '\t' --sort median:n bench.csv | column -t -s $'\t'
command               mean   median  runs
xxhsum -H128 big.iso  0.061  0.060   10
cksum big.iso         0.187  0.190   10
b2sum big.iso         0.298  0.301   10
md5sum big.iso        0.351  0.349   10
sha256sum big.iso     0.412  0.405   10
```

A field that holds a quote is still quoted, and `column` shows the quotes.  A field that holds a tab or a line break misaligns the table, because `column` splits the field at the tab and starts a new row at the line break.  The CSV is still correct, but the table is not.

### Debugging

`--debug` explains how csvv read each option, and warns about questionable usage, such as a numeric filter that met cells that are not numbers.  It writes only to stderr, so the output stays valid CSV.

```
$ csvv --debug -H -e 'median<0.35' --sort median:nr --select command,median bench.csv >/dev/null
csvv: -e 'median<0.35': column 3 ('median') < 0.35, comparing numbers
csvv: --sort 'median:nr': column 3 ('median'), as numbers, reversed
csvv: sorting holds every row in memory
csvv: --select 'command': column 1 ('command')
csvv: --select 'median': column 3 ('median')
csvv: rows read: 5, kept by the filter: 4, written: 4 (not counting the header)
```

## Behavior worth knowing

- **Values are never rewritten.**  csvv converts a value only to compare it, so `007`, `1e5`, and `0.037180646437500006` come out byte for byte.  Quoting can change, though: a needlessly quoted field is written without quotes.
- **With `-H`, the header is written first**, even when no row passes the filter.  Pipe the output to `tail -n +2` to drop it, unless a quoted header field spans lines.
- **Malformed quoting is an error**, as in `"quoted" word`, rather than being silently repaired.  Error messages name the file, the record, and the line where that record starts.
- **Every record must be as long as the first.**  `--ragged pad` fills out a short record with empty fields, and `--ragged truncate` cuts a long one, but each still rejects the other kind.  Blank lines are skipped.
- **Input is UTF-8**, and a byte-order mark is dropped.  Bytes that are not valid UTF-8 pass through unchanged.  Output lines end with `\n`.
- **The exit status** is 0 on success, 1 on a data or file error, 2 on a usage error, and 130 on Ctrl-C.  A filter that keeps no rows still exits 0, unlike `grep`.

## Development

The tool itself needs only the standard library.  `make check` runs ruff, pylint, and mypy, then the tests with pytest, so it needs all four.

## License

csvv is licensed under the Mozilla Public License 2.0 (MPL-2.0).

## The name

csvv began as "CSV viewer".  The initial plan had eleven subcommands, one of which, `view`, showed CSV as an aligned table.  As the design took shape, csvv narrowed to the three jobs no standard command does with CSV: filtering, sorting, and selecting columns by name.  The name stayed.  If the second v needs a meaning, read it as the verb *vet*, as in vetting candidates: to examine carefully and keep only what passes.
