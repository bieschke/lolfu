#!/usr/bin/env python3.4
"""Read a simple match CSV on stdin and write a complex match ARFF file to stdout.
"""

import csv
import riot
import sys
import urllib.error


def main():
    api = riot.RiotAPI()

    # infer the keys for overall stats
    some_summoner_id = list(api.bootstrap_summoner_ids)[0]
    overall_stats = api.summoner_champion_stats(some_summoner_id, riot.CHAMPION_OVERALL)
    overall_stats_keys = tuple(sorted(overall_stats.keys()))

    # infer the keys for champion specific stats
    for champion_stats in api.summoner_stats(some_summoner_id)['champions']:
        if champion_stats['id'] != riot.CHAMPION_OVERALL:
            champion_stats_keys = tuple(sorted(champion_stats['stats'].keys()))
            break

    # ARFF metadata
    print('@RELATION lol_match_complex')
    print()
    print('@ATTRIBUTE match_timestamp NUMERIC')
    for position in ('top', 'jungle', 'mid', 'adc', 'support'):
        print('@ATTRIBUTE %s_champion %s' % (position, riot.RIOT_CHAMPION_KEYS))
        print('@ATTRIBUTE %s_enemy %s' % (position, riot.RIOT_CHAMPION_KEYS))
        for key in overall_stats_keys:
            print('@ATTRIBUTE %s_overall_%s NUMERIC' % (position, key))
        for key in champion_stats_keys:
            print('@ATTRIBUTE %s_champion_%s NUMERIC' % (position, key))
    print('@ATTRIBUTE victory {WIN,LOSS}')
    print()
    print('@DATA')

    # walk simple matches from stdin
    matches = {}
    for row in csv.reader(sys.stdin):
        row = list(map(int, row))
        match_timestamp = row[1]

        for victory, team, enemy in (
                ('WIN', row[2:12], (row[13], row[15], row[17], row[19], row[21])),
                ('LOSS', row[12:], (row[3], row[5], row[7], row[9], row[11])),
                ):
            top_summoner_id, top_champion_id, \
                jungle_summoner_id, jungle_champion_id, \
                mid_summoner_id, mid_champion_id, \
                adc_summoner_id, adc_champion_id, \
                support_summoner_id, support_champion_id = team
            top_enemy_id, jungle_enemy_id, mid_enemy_id, adc_enemy_id, support_enemy_id = enemy

            try:
                output = [match_timestamp]

                for summoner_id, champion_id, enemy_id in (
                        (top_summoner_id, top_champion_id, top_enemy_id),
                        (jungle_summoner_id, jungle_champion_id, jungle_enemy_id),
                        (mid_summoner_id, mid_champion_id, mid_enemy_id),
                        (adc_summoner_id, adc_champion_id, adc_enemy_id),
                        (support_summoner_id, support_champion_id, support_enemy_id),
                        ):

                    output.append(api.champion_key(champion_id))
                    output.append(api.champion_key(enemy_id))

                    overall_stats = api.summoner_champion_stats(summoner_id, riot.CHAMPION_OVERALL)
                    for key in overall_stats_keys:
                        output.append(int(overall_stats.get(key, 0)))

                    champion_stats = api.summoner_champion_stats(summoner_id, champion_id)
                    for key in champion_stats_keys:
                        output.append(int(champion_stats.get(key, 0)))

                output.append(victory)

                print(','.join([str(i) for i in output]))

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue # skip records that contain missing data
                else:
                    raise


if __name__ == '__main__':
    main()
