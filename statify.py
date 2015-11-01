#!/usr/bin/env python3.4
"""Read CSV kill stats on stdin and output JS kill stats on stdout.
"""

import csv
import sys

reader = csv.reader(sys.stdin)

print('var stats = {');
for winp, matches, wins, losses, us_kills, them_kills in reader:
    print('"[%d,%d]" : [%d,%d],' % (int(us_kills), int(them_kills), int(wins), int(losses)))
print('};');
