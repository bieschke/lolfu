#!/usr/bin/env python

import argparse
import json
import riot
import sys

positions = ('top', 'jungle', 'mid', 'adc', 'support')

def main(matchup_csv, synergy_csv):

    # accept an optional champion matchup winrate CSV
    matchups = {}
    if matchup_csv:
        for line in matchup_csv:
            champion1, champion2, winrate = line.split(',')
            matchups[champion1, champion2] = float(winrate)
        print >>sys.stderr, '%d matchups' % len(matchups)

    # accept an optional champion synergy winrate CSV
    synergies = {}
    if synergy_csv:
        for line in synergy_csv:
            champion1, champion2, winrate = line.split(',')
            synergies[champion1, champion2] = float(winrate)
        print >>sys.stderr, '%d synergies' % len(synergies)

    print '@RELATION lol_match_aggregated'
    print
    for position in positions:
        print '@ATTRIBUTE %s_champion %s' % (position, riot.RIOT_CHAMPION_KEYS)
        print '@ATTRIBUTE %s_enemy %s' % (position, riot.RIOT_CHAMPION_KEYS)
        print '@ATTRIBUTE %s_sessions NUMERIC' % position
        print '@ATTRIBUTE %s_winrate NUMERIC' % position
        print '@ATTRIBUTE %s_kda NUMERIC' % position
        print '@ATTRIBUTE %s_df NUMERIC' % position
    print '@ATTRIBUTE victory {WIN,LOSS}'
    print
    print '@DATA'
    for line in sys.stdin:
        row = json.loads(line)
        output = []
        for position in positions:
            champion = row['%s_champion' % position]
            enemy = row['%s_enemy' % position]
            wins = int(row['%s_champion_totalSessionsWon' % position])
            sessions = int(row['%s_champion_totalSessionsPlayed' % position])
            winrate = 0.0
            if sessions > 0:
                winrate = float(wins) / sessions
            kills = int(row['%s_champion_totalChampionKills' % position])
            deaths = int(row['%s_champion_totalDeathsPerSession' % position])
            assists = int(row['%s_champion_totalAssists' % position])
            kda = float(kills + assists) / max(deaths, 1) # avoid divide by zero
            df = (kills * 2) + (deaths * -3) + (assists * 1)
            victory = row['victory']
            output.extend([champion, enemy, sessions, winrate, kda, df])
        output.append(row['victory'])
        print ','.join(map(str, output))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--matchupfile', metavar='MATCHUP_CSV', type=argparse.FileType('r'), default=None)
    parser.add_argument('--synergyfile', metavar='SYNERGY_CSV', type=argparse.FileType('r'), default=None)
    args = parser.parse_args()
    main(args.matchupfile, args.synergyfile)
