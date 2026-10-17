.PHONY: all clean

all: csvv.1

csvv.1: csvv
	help2man --no-info --output=$@ \
		--name='filter and sort the rows of a CSV file, and select its columns' ./csvv

clean:
	rm -f csvv.1
