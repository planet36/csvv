.PHONY: all check test lint clean

all: csvv.1

csvv.1: csvv
	help2man --no-info --output=$@ \
		--name='filter and sort the rows of a CSV file, and select its columns' ./csvv

check: lint test

test:
	pytest

lint:
	ruff check csvv tests
	pylint csvv tests/*.py
	mypy --ignore-missing-imports csvv

clean:
	rm -f csvv.1
