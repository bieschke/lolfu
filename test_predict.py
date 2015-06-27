#!/usr/bin/env python
"""Work-in-progress
"""

import csv
import riot
import sys


winrate_cache = {}
def summoner_champion_winrate(api, summoner_id, champion_id):
    if summoner_id not in winrate_cache:
        winrate_cache[summoner_id] = {}
        for champion in api.summoner_stats(summoner_id).get('champions', []):
            stats = champion['stats']
            won = stats['totalSessionsWon']
            played = stats['totalSessionsPlayed']
            winrate_cache[summoner_id][champion['id']] = float(won) / played
    return winrate_cache[summoner_id].get(champion_id, 0.0)

def main():
    api = riot.RiotAPI()

    # collect all matches from stdin
    matches = {}
    for row in csv.reader(sys.stdin):
        match_id = int(row[0])
        summoner_id = int(row[1])
        champion_id = int(row[2])
        winner = bool(row[-1] == 'True')
        matches.setdefault((match_id, winner), []).append((summoner_id, champion_id))

    # walk through all matches evaluating our win predictions
    total_predictions = 0
    correct_predictions = 0
    for (match_id, winner), participants in matches.iteritems():
        assert len(participants) == 5, `(match_id, winner)`
        summed = 0.0
        for summoner_id, champion_id in participants:
            summed += summoner_champion_winrate(api, summoner_id, champion_id)
            print 'summed=%s'%summed
        predict_win = summed > 2.5
        if winner == predict_win:
            correct_predictions += 1
        print summed
        total_predictions +=1

        # how'd we do?
        print 'Predicted Correctly %.0f%% (%d of %d)' % (100.0 * correct_predictions / total_predictions, correct_predictions, total_predictions)

if __name__ == '__main__':
    main()
