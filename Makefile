# SPDX-FileCopyrightText: Steven Ward
# SPDX-License-Identifier: MPL-2.0

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
MANDIR ?= $(PREFIX)/share/man
MAN1DIR ?= $(MANDIR)/man1

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

install: csvv $(MAN)
	@install -D --verbose --mode=755 --target-directory=$(DESTDIR)$(BINDIR) -- csvv
	@install -D --verbose --mode=644 --target-directory=$(DESTDIR)$(MAN1DIR) -- $(MAN)

uninstall:
	@$(RM) --verbose -- $(DESTDIR)$(BINDIR)/csvv
	@$(RM) --verbose -- $(DESTDIR)$(MAN1DIR)/$(MAN)

# https://www.gnu.org/software/make/manual/make.html#Phony-Targets
.PHONY: all man check test lint clean install uninstall

# https://www.gnu.org/software/make/manual/html_node/Special-Targets.html#index-removing-targets-on-failure
.DELETE_ON_ERROR:
