#!/usr/bin/env python3.4
"""Read a complex match as a JSON dict on stdin and output a denormalized
synergy ARFF on stdout. Synergy data captures all champion combinations
possible on one team.

The following fields are in this ARFF:

champion1 = Champion being played on your team.
champion2 = Champion being played on your team.
victory = Was this match a "WIN" or "LOSS"?
"""

import json
from . import riot
import sys

positions = ('top', 'jungle', 'mid', 'adc', 'support')

def main():
    print('@RELATION lol_synergy')
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
            champion1 = row['%s_champion' % position1]
            for position2 in positions:
                if position1 == position2:
                    continue # skip our own position
                champion2 = row['%s_champion' % position2]
                print(','.join([champion1, champion2, victory]))

if __name__ == '__main__':
    main()
