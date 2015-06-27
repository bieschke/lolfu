#!/usr/bin/env python
"""Read a simple match CSV on stdin and write a complex match ARFF file to stdout.
"""

import csv
import riot
import sys
import urllib2


champion_cache = {}
def champion_key(api, champion_id):
    """Return the text key for the given champion. Results are memoized."""
    if not champion_cache:
        for champion in api.champions()['data'].values():
            champion_cache[champion['id']] = champion['key']
    return champion_cache[champion_id]


stats_cache = {}
def summoner_stats(api, summoner_id):
    """Return stats for the given summoner. Results are memoized."""
    if summoner_id not in stats_cache:
        my_stats = {}
        for champion in api.summoner_stats(summoner_id).get('champions', []):
            my_stats[champion['id']] = champion['stats']
        stats_cache[summoner_id] = my_stats
    return stats_cache[summoner_id]


def summoner_champion_stats(api, summoner_id, champion_id):
    """Return the summoner's champion specific stats."""
    return summoner_stats(api, summoner_id).get(champion_id, {})


def main():
    api = riot.RiotAPI()

    # infer the keys for overall and champion-specific stats
    some_summoner_id = list(api.bootstrap_summoner_ids)[0]
    some_summoner_stats = summoner_stats(api, some_summoner_id)
    overall_stats_keys = sorted(some_summoner_stats[0].keys())
    some_champion_ids = some_summoner_stats.keys()
    some_champion_ids.remove(0)
    champion_stats_keys = sorted(some_summoner_stats[some_champion_ids[0]].keys())

    # ARFF metadata
    print '@RELATION lol_match_complex'
    print
    print '@ATTRIBUTE match_timestamp NUMERIC'
    for position in ('top', 'jungle', 'mid', 'adc', 'support'):
        print '@ATTRIBUTE %s_champion %s' % (position, riot.RIOT_CHAMPION_KEYS)
        print '@ATTRIBUTE %s_enemy %s' % (position, riot.RIOT_CHAMPION_KEYS)
        for key in overall_stats_keys:
            print '@ATTRIBUTE %s_overall_%s NUMERIC' % (position, key)
        for key in champion_stats_keys:
            print '@ATTRIBUTE %s_champion_%s NUMERIC' % (position, key)
    print '@ATTRIBUTE victory {WIN,LOSS}'
    print
    print '@DATA'

    # walk simple matches from stdin
    matches = {}
    for row in csv.reader(sys.stdin):
        row = map(int, row)
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

                    output.append(champion_key(api, champion_id))
                    output.append(champion_key(api, enemy_id))

                    overall_stats = summoner_champion_stats(api, summoner_id, 0)
                    for key in overall_stats_keys:
                        output.append(int(overall_stats.get(key, 0)))

                    champion_stats = summoner_champion_stats(api, summoner_id, champion_id)
                    for key in champion_stats_keys:
                        output.append(int(champion_stats.get(key, 0)))

                output.append(victory)

                print ','.join([str(i) for i in output])

            except urllib2.HTTPError as e:
                if e.code == 404:
                    continue # skip records that contain missing data
                else:
                    raise


if __name__ == '__main__':
    main()
