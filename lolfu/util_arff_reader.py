#!/usr/bin/env python3.4
"""Read an ARFF file from stdin and output this data into different
formats on stdout.

For CSV output the data lines are passed through without modification
and all other lines are removed.

For JSON output each data line is mapped into a dictionary where the
ARFF attribute names become the keys and data becomes the values.
"""

import argparse
import csv
import json
import sys


CSV = 'csv'
JSON = 'json'


def main(output):

    # CSV output
    if output == CSV:
        for line in sys.stdin:
            if not line.strip() or line.startswith('@'):
                pass
            else:
                print(line, end='') # remember to omit trailing return

    # JSON output
    elif output == JSON:
        attributes = []
        for row in csv.reader(sys.stdin):
            if not row or row[0].startswith('@RELATION') or row[0].startswith('@DATA'):
                pass # ignore these lines
            elif row[0].startswith('@ATTRIBUTE'):
                # attribute names between keys in our JSON output
                attribute_name = row[0].split()[1]
                attributes.append(attribute_name)
            else:
                # data becomes values in our JSON output
                print(json.dumps(dict(list(zip(attributes, row)))))

    # Unknown output
    else:
        raise ValueError('Unknown output format: %r' % output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', metavar='FORMAT', default='csv', choices=(CSV, JSON))
    args = parser.parse_args()
    main(args.output)
