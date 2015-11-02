#!/usr/bin/env python3.4
"""Read CSV stats and output JS stats.
"""

import csv

with open('kill_stats.js', 'w') as outfile:
    with open('kill_stats.csv', newline='') as f:
        print('var kill_stats = {', file=outfile);
        for winp, matches, wins, losses, us_kills, them_kills in csv.reader(f):
            print('"[%d,%d]" : [%d,%d],' % (int(us_kills), int(them_kills), int(wins), int(losses)), file=outfile)
        print('};', file=outfile);

with open('tower_stats.js', 'w') as outfile:
    with open('tower_stats.csv', newline='') as f:
        print('var tower_stats = {', file=outfile);
        for winp, matches, wins, losses, us_inhibs, us_towers, them_inhibs, them_towers in csv.reader(f):
            print('"[%d,%d,%d,%d]" : [%d,%d],' % tuple(int(x) for x in (us_inhibs, us_towers, them_inhibs, them_towers, wins, losses)), file=outfile)
        print('};', file=outfile);

with open('joint_stats.js', 'w') as outfile:
    with open('joint_stats.csv', newline='') as f:
        print('var joint_stats = {', file=outfile);
        for winp, matches, wins, losses, us_inhibs, us_towers, us_kills, them_inhibs, them_towers, them_kills in csv.reader(f):
            print('"[%d,%d,%d,%d,%d,%d]" : [%d,%d],' % tuple(int(x) for x in (us_inhibs, us_towers, us_kills, them_inhibs, them_towers, them_kills, wins, losses)), file=outfile)
        print('};', file=outfile);
