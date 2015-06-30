#!/usr/bin/env python3.4
"""Read a complex match as a JSON dict on stdin and output a denormalized
matchup ARFF on stdout. Matchup data captures all champion combinations
between one team against another.

The following fields are in this ARFF:

champion1 = Champion being played on your team.
champion2 = Champion being played on opposing team.
victory = Was this match a "WIN" or "LOSS"?
"""

import json
from . import riot
import sys

positions = ('top', 'jungle', 'mid', 'adc', 'support')

def main():
    print('@RELATION lol_matchup')
    print()
    print('@ATTRIBUTE champion1 %s' % riot.RIOT_CHAMPION_KEYS)
    print('@ATTRIBUTE champion2 %s' % riot.RIOT_CHAMPION_KEYS)
    print('@ATTRIBUTE victory {WIN,LOSS}')
    print()
    print('@DATA')
    for line in sys.stdin:
        row = json.loads(line)
        victory = row['victory']
        for position1 in positions:
            champion = row['%s_champion' % position1]
            for position2 in positions:
                enemy = row['%s_enemy' % position2]
                print(','.join([champion, enemy, victory]))

if __name__ == '__main__':
    main()
