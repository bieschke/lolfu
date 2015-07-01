#!/usr/bin/env python3.4
"""Read a complex match JSON and write an aggregated match ARFF to stdout.
"""

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
        print('%d matchups' % len(matchups), file=sys.stderr)

    # accept an optional champion synergy winrate CSV
    synergies = {}
    if synergy_csv:
        for line in synergy_csv:
            champion1, champion2, winrate = line.split(',')
            synergies[champion1, champion2] = float(winrate)
        print('%d synergies' % len(synergies), file=sys.stderr)

    print('@RELATION lol_match_aggregated')
    print()
    print('@ATTRIBUTE top_with_jungle NUMERIC')
    print('@ATTRIBUTE top_with_mid NUMERIC')
    print('@ATTRIBUTE top_with_adc NUMERIC')
    print('@ATTRIBUTE top_with_support NUMERIC')
    print('@ATTRIBUTE jungle_with_mid NUMERIC')
    print('@ATTRIBUTE jungle_with_adc NUMERIC')
    print('@ATTRIBUTE jungle_with_support NUMERIC')
    print('@ATTRIBUTE mid_with_adc NUMERIC')
    print('@ATTRIBUTE mid_with_support NUMERIC')
    print('@ATTRIBUTE adc_with_support NUMERIC')
    for position in positions:
        print('@ATTRIBUTE %s_champion %s' % (position, riot.RIOT_CHAMPION_KEYS))
        print('@ATTRIBUTE %s_enemy %s' % (position, riot.RIOT_CHAMPION_KEYS))
        print('@ATTRIBUTE %s_sessions NUMERIC' % position)
        print('@ATTRIBUTE %s_winrate NUMERIC' % position)
        print('@ATTRIBUTE %s_kda NUMERIC' % position)
        print('@ATTRIBUTE %s_df NUMERIC' % position)
        for position2 in positions:
            print('@ATTRIBUTE %s_vs_%s NUMERIC' % (position, position2))
    print('@ATTRIBUTE victory {WIN,LOSS}')
    print()

    print('@DATA')
    for line in sys.stdin:
        row = json.loads(line)
        output = []

        top_champion = row['top_champion']
        jungle_champion = row['jungle_champion']
        mid_champion = row['mid_champion']
        adc_champion = row['adc_champion']
        support_champion = row['support_champion']
        output.append(synergies.get((top_champion, jungle_champion), '?'))
        output.append(synergies.get((top_champion, mid_champion), '?'))
        output.append(synergies.get((top_champion, adc_champion), '?'))
        output.append(synergies.get((top_champion, support_champion), '?'))
        output.append(synergies.get((jungle_champion, mid_champion), '?'))
        output.append(synergies.get((jungle_champion, adc_champion), '?'))
        output.append(synergies.get((jungle_champion, support_champion), '?'))
        output.append(synergies.get((mid_champion, adc_champion), '?'))
        output.append(synergies.get((mid_champion, support_champion), '?'))
        output.append(synergies.get((adc_champion, support_champion), '?'))

        for position in positions:
            champion = row['%s_champion' % position]
            enemy = row['%s_enemy' % position]
            output.extend([champion, enemy])

            wins = int(row['%s_champion_totalSessionsWon' % position])
            sessions = int(row['%s_champion_totalSessionsPlayed' % position])
            winrate = 0.0
            if sessions > 0:
                winrate = float(wins) / sessions
            output.extend([sessions, winrate])

            kills = int(row['%s_champion_totalChampionKills' % position])
            deaths = int(row['%s_champion_totalDeathsPerSession' % position])
            assists = int(row['%s_champion_totalAssists' % position])
            kda = float(kills + assists) / max(deaths, 1) # avoid divide by zero
            df = (kills * 2) + (deaths * -3) + (assists * 1)
            output.extend([kda, df])

            for position2 in positions:
                matchup_champion = row['%s_enemy' % position2]
                matchup_winrate = matchups.get((champion, matchup_champion), '?')
                output.append(matchup_winrate)

        output.append(row['victory'])
        print(','.join(map(str, output)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--matchupfile', metavar='MATCHUP_CSV', type=argparse.FileType('r'), default=None)
    parser.add_argument('--synergyfile', metavar='SYNERGY_CSV', type=argparse.FileType('r'), default=None)
    args = parser.parse_args()
    main(args.matchupfile, args.synergyfile)
