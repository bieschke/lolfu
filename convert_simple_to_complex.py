#!/usr/bin/env python
"""Read a match_simple CSV on stdin and write a match_complex ARFF file to stdout.
"""

import csv
import riot
import sys
import urllib2


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
    return summoner_stats(api, summoner_id).get(champion_id, {})

def main():
    api = riot.RiotAPI()

    # ARFF metadata
    print '@RELATION lol_match_complex'
    print
    print '@ATTRIBUTE match_creation NUMERIC'
    some_summoner_id = list(api.bootstrap_summoner_ids)[0]
    for position in ('top', 'jungle', 'mid', 'adc', 'support'):
        some_summoner_stats = summoner_stats(api, some_summoner_id)
        overall_stats_keys =  sorted(some_summoner_stats[0].keys())
        for key in overall_stats_keys:
            print '@ATTRIBUTE %s_overall_%s NUMERIC' % (position, key)
        #print '@ATTRIBUTE %s_champion {MonkeyKing,Jax,Shaco,Warwick,Nidalee,Zyra,Brand,Rammus,Corki,Braum,Anivia,Tryndamere,MissFortune,Blitzcrank,Yorick,Xerath,Sivir,Riven,Orianna,Gangplank,Malphite,Poppy,Karthus,Jayce,Nunu,Trundle,Sejuani,Graves,Morgana,Gnar,Lux,Shyvana,Renekton,Fiora,Jinx,Kalista,Fizz,Kassadin,Sona,Irelia,Viktor,Cassiopeia,Maokai,Thresh,Kayle,Hecarim,Khazix,Olaf,Ziggs,Syndra,DrMundo,Karma,Annie,Akali,Leona,Yasuo,Kennen,Rengar,Ryze,Shen,Zac,Pantheon,Swain,Bard,Sion,Vayne,Nasus,TwistedFate,Chogath,Udyr,Lucian,Volibear,Caitlyn,Darius,Nocturne,Zilean,Azir,Rumble,Skarner,Teemo,Urgot,Amumu,Galio,Heimerdinger,Ashe,Velkoz,Singed,Varus,Twitch,Garen,Diana,MasterYi,Elise,Alistar,Katarina,Ekko,Mordekaiser,KogMaw,Aatrox,Draven,FiddleSticks,Talon,XinZhao,LeeSin,Taric,Malzahar,Lissandra,Tristana,RekSai,Vladimir,JarvanIV,Nami,Soraka,Veigar,Janna,Nautilus,Evelynn,Gragas,Zed,Vi,Lulu,Ahri,Quinn,Leblanc,Ezreal}' % position
        some_champion_ids = some_summoner_stats.keys()
        some_champion_ids.remove(0)
        champion_stats_keys = sorted(some_summoner_stats[some_champion_ids[0]].keys())
        for key in champion_stats_keys:
            print '@ATTRIBUTE %s_champion_%s NUMERIC' % (position, key)
    print '@ATTRIBUTE victory {WIN,LOSS}'
    print
    print '@DATA'

    # walk simple matches from stdin
    matches = {}
    for row in csv.reader(sys.stdin):
        match_creation = int(row[0])
        top_summoner_id = int(row[1])
        top_champion_id = int(row[2])
        jungle_summoner_id = int(row[3])
        jungle_champion_id = int(row[4])
        mid_summoner_id = int(row[5])
        mid_champion_id = int(row[6])
        adc_summoner_id = int(row[7])
        adc_champion_id = int(row[8])
        support_summoner_id = int(row[9])
        support_champion_id = int(row[10])
        victory = row[11]

        try:
            output = [match_creation]

            for summoner_id, champion_id in (
                    (top_summoner_id, top_champion_id),
                    (jungle_summoner_id, jungle_champion_id),
                    (mid_summoner_id, mid_champion_id),
                    (adc_summoner_id, adc_champion_id),
                    (support_summoner_id, support_champion_id),
                    ):

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
                continue # skip records that rely on missing data
            else:
                raise


if __name__ == '__main__':
    main()
