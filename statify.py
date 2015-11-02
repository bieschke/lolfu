#!/usr/bin/env python3.4
"""Read CSV kill stats on stdin and output JS kill stats on stdout.
"""

import csv

with open('kill_stats.js', 'w') as outfile:
    with open('kill_stats.csv', newline='') as f:
        print('var stats = {', file=outfile);
        for winp, matches, wins, losses, us_kills, them_kills in csv.reader(f):
            print('"[%d,%d]" : [%d,%d],' % (int(us_kills), int(them_kills), int(wins), int(losses)), file=outfile)
        print('};', file=outfile);

with open('tower_stats.js', 'w') as outfile:
    with open('tower_stats.csv', newline='') as f:
        print('var stats = {', file=outfile);
        for winp, matches, wins, losses, us_inhibs, us_towers, them_inhibs, them_towers in csv.reader(f):
            print('"[%d,%d,%d,%d]" : [%d,%d],' % tuple(int(x) for x in (us_inhibs, us_towers, them_inhibs, them_towers, wins, losses)), file=outfile)
        print('};', file=outfile);
