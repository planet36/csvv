# SPDX-FileCopyrightText: Steven Ward
# SPDX-License-Identifier: MPL-2.0

MAN = csvv.1
# The first line of the --help description, lowercase and with no period.
MAN_NAME = filter and sort the rows of a CSV file, and select its columns

all: test

man: $(MAN)

$(MAN): csvv Makefile
	help2man --no-info --locale=C.UTF-8 --name='$(MAN_NAME)' --output=$@ ./$<

check: lint test

test:
	pytest

lint:
	ruff check csvv tests
	pylint csvv tests/*.py
	mypy --ignore-missing-imports csvv
	mypy --ignore-missing-imports tests

clean:
	@$(RM) --recursive -- \
		$(MAN) \
		__pycache__ \
		tests/__pycache__ \
		.mypy_cache \
		.pytest_cache \
		.ruff_cache

# https://www.gnu.org/software/make/manual/make.html#Phony-Targets
.PHONY: all man check test lint clean

# https://www.gnu.org/software/make/manual/html_node/Special-Targets.html#index-removing-targets-on-failure
.DELETE_ON_ERROR:
