# csvv

Filter, sort, and select columns of CSV files, in one dependency-free Python script.

csvv does a little of what `awk`, `sort`, and `cut` do, but it understands CSV.  A quoted field may hold commas, quotes, and line breaks, and csvv still reads it as one field.  With a header, columns can be named instead of counted.  Every value is written back exactly as it was read.

## Example

Given `bench.csv`:

```
command,mean,median,runs
sha256sum big.iso,0.412,0.405,10
b2sum big.iso,0.298,0.301,10
md5sum big.iso,0.351,0.349,10
cksum big.iso,0.187,0.190,10
"xxhsum -H128 big.iso",0.061,0.060,10
```

keep the rows whose median is under 0.35, sort them from slowest to fastest, and print two columns:

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

csvv needs Python 3.12 or later, and nothing else.  Copy the script somewhere on your `PATH`:

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
| `-o, --output-delimiter CHAR` | the output field separator (default: the input separator) |
| `--ragged MODE` | handle a record whose length differs from the first: `error` (the default), `pad`, or `truncate` |
| `-e, --filter EXPR` | keep only rows matching EXPR (repeatable) |
| `--sort KEY` | sort rows by KEY (repeatable) |
| `--select LIST` | output only the columns in LIST, in that order (repeatable) |
| `--debug` | print diagnostics and warnings to stderr |
| `-h, --help` | show the help and exit |
| `-V, --version` | show the version and exit |

CHAR is one character, or `\t` for a tab.  `csvv --help` and `man csvv` give the full details.

### Naming columns

A column is named by its position, by a slice, or with `-H` by its name in the header.

- **Positions start at 1**, as in `cut` and `awk`, and negative ones count from the end, so `-1` is the last column.
- **A slice is `START:STOP:STEP`**, as in Python, except that STOP is included, as in `cut -f2-4`.  So `2:4` is columns 2, 3, and 4, `4:` runs from column 4 to the end, and `::-1` is every column in reverse.
- **With `-H`, an exact column name wins over a position.**  A `#` prefix forces a position, so `#3` always means the third column, even when the header has a column named `3`.

Write `--select=-1` rather than `--select -1` when the value starts with `-`, and likewise for `-e` and `--sort`.

### Filtering

`-e` takes `COL OP VALUE`, where OP is one of `==`, `!=`, `<`, `<=`, `>`, `>=`, `~`, or `!~`.  A row must match every `-e`.

- **`~` and `!~`** test whether the regex VALUE is found anywhere in the cell.
- **The other operators compare numbers when VALUE is a number**, and text otherwise.  So `err==99` matches `99`, `99.0`, and `099`.  For an exact text match, use a regex, as in `id~^007$`.
- **In a numeric test, a cell that is not a number fails** every operator but `!=`.

The expression is parsed by a small fixed grammar, never evaluated as code.

```
$ csvv -H -e 'command~^(md5|sha)' --select 1,3 bench.csv
command,median
sha256sum big.iso,0.405
md5sum big.iso,0.349
```

### Sorting

`--sort` takes `COL[:FLAGS]`, where FLAGS holds `n` to compare numbers, `r` to reverse, or both, as in `median:nr`.

- **The sort is stable**, and the first `--sort` takes priority over the next.
- **A slice stands for one key per column**, so `--sort 2:4:n` sorts by column 2, then 3, then 4, all as numbers.
- **In a numeric key, cells that are not numbers sort after the numbers**, in either direction.
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

A field that holds a tab, a quote, or a line break is still quoted, and `column` shows the quotes.

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
- **With `-H`, the header is written first**, even when no row passes the filter.  Pipe the output to `tail -n +2` to drop it.
- **Malformed quoting is an error**, as in `"quoted" word`, rather than being silently repaired.  Error messages name the record and the line where it starts.
- **Every record must be as long as the first**, unless `--ragged` says to pad or truncate it.  Blank lines are skipped.
- **Input is UTF-8**, and a byte-order mark is dropped.  Bytes that are not valid UTF-8 pass through unchanged.  Output lines end with `\n`.
- **The exit status** is 0 on success, 1 on a data or file error, 2 on a usage error, and 130 on Ctrl-C.  A filter that keeps no rows still exits 0, unlike `grep`.

## Development

`make check` runs ruff, pylint, and mypy, then the pytest tests.  The tool itself needs nothing beyond the standard library.  The tests and the checks need pytest, ruff, pylint, and mypy.

## License

csvv is licensed under the Mozilla Public License 2.0 (MPL-2.0).

## The name

csvv began as "CSV viewer."  The initial plan had eleven subcommands, one of which, `view`, showed CSV as an aligned table.  As the design took shape, csvv narrowed to the three jobs no standard command does with CSV: filtering, sorting, and selecting columns by name.  The name stayed.  If the second v needs a meaning, read it as the verb *vet*, as in vetting candidates: to examine carefully and keep only what passes.
