# SPDX-FileCopyrightText: Steven Ward
# SPDX-License-Identifier: MPL-2.0

MAN = csvv.1
MAN_NAME = filter and sort the rows of a CSV file, and select its columns

all: $(MAN)

man: $(MAN)

$(MAN): csvv
	@command -v help2man >/dev/null || { echo 'make man: help2man is required' >&2; exit 1; }
	help2man --no-info --locale=C.UTF-8 --name='$(MAN_NAME)' --output=$@ ./$<

check: lint test

test:
	pytest

lint:
	ruff check csvv tests
	pylint csvv tests/*.py
	mypy --ignore-missing-imports csvv

clean:
	@$(RM) --verbose -- $(MAN)

# https://www.gnu.org/software/make/manual/make.html#Phony-Targets
.PHONY: all man check test lint clean

# https://www.gnu.org/software/make/manual/html_node/Special-Targets.html#index-removing-targets-on-failure
.DELETE_ON_ERROR:
