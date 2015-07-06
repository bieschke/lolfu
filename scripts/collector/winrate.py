#!/usr/bin/env python3.4
"""Read a simple match as a JSON dict on stdin and output tier-position-champion winrates.
"""

import argparse
import json
import riot
import sys

positions = [p.lower() for p in riot.POSITIONS]


def main(minsample):

    # accumulate session and win counts
    sessions = {}
    wins = {}
    for line in sys.stdin:
        row = json.loads(line)
        for victor in ('winner', 'loser'):
            for position in positions:
                tier = row['%s_%s_tier' % (victor, position)]
                champion_id = row['%s_%s_champion_id' % (victor, position)]
                sessions.setdefault(tier, {}).setdefault(position, {}).setdefault(champion_id, 0)
                sessions[tier][position][champion_id] += 1
                if victor == 'winner':
                    wins.setdefault(tier, {}).setdefault(position, {}).setdefault(champion_id, 0)
                    wins[tier][position][champion_id] += 1

    # output CSV line for every position-tier-champion combination
    for tier in sessions:
        for position in sessions[tier]:
            for champion_id in sessions[tier][position]:
                session_count = sessions[tier][position][champion_id]
                if minsample <= session_count:
                    win_count = wins.get(tier, {}).get(position, {}).get(champion_id, 0)
                    winrate = float(win_count) / session_count
                    print(','.join([tier, position, champion_id, str(winrate)]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--minsample', metavar='N', type=int, default=0,
        help='require at least N samples in order to include winrate')
    args = parser.parse_args()
    main(args.minsample)
