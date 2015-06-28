#!/usr/bin/env python
"""Read matchup or synergy data as CSV on stdin and output data
in the following format: champion1,champion2,winrate
"""

import csv
import sys

def main():

    # accumulate win and session counts
    wins = {}
    sessions = {}
    for champion1, champion2, victory in csv.reader(sys.stdin):
        key = (champion1, champion2)
        sessions[key] = sessions.get(key, 0) + 1
        if bool(victory == 'WIN'):
            wins[key] = wins.get(key, 0) + 1

    # output CSV line for every champion-champion combination
    for key in sessions.keys():
        win_count = wins.get(key, 0)
        session_count = sessions[key]
        winrate = float(win_count) / session_count
        print ','.join([key[0], key[1], str(winrate)])


if __name__ == '__main__':
    main()
