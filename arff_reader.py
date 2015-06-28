#!/usr/bin/env python
"""Read an ARFF file from stdin and output a JSON object with
attribute names as keys and the data as values to stdout. All
values in resulting JSON object will be expressed as strings.
"""

import csv
import json
import sys


def main():
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
            print json.dumps(dict(zip(attributes, row)))


if __name__ == '__main__':
    main()
