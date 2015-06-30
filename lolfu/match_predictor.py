#!/usr/bin/env python3.4
"""Utility to lookup all of the summoner-champion pairs in your current
lobby. This program will respond with a textual predictions about their
chances of winning the match.

Example usage:

eric$ ./dodge.py wudini fiddlesticks thenakedbacon azir zacefronscolon irelia matasar thresh bunglersbane kalista
Wudini on Fiddlesticks winrate 55%
TheNakedBacon on Azir winrate 0%
Zac Efrons Colon on Irelia winrate 0%
matasar on Thresh winrate 51%
Bunglers Bane on Kalista winrate 0%
AVERAGE WINRATE 21%
"""

from . import riot
import sys

def main():
    assert len(sys.argv) == 11, 'USAGE %s <summoner1 champion1> ... X5' % sys.argv[0]
    summoner1, champion1, summoner2, champion2, summoner3, champion3, summoner4, \
        champion4, summoner5, champion5 = sys.argv[1:]

    api = riot.RiotAPI()

    # cache a single map that allows you to lookup a champion by it's
    # key, title, or name
    champion_map = {}
    champions = api.champions()
    for champion in list(champions['data'].values()):
        champion_id = champion['id']
        champion_name = champion['name']
        champion_map[str(champion_id)] = (champion_id, champion_name)
        champion_map[champion['key'].lower()] = (champion_id, champion_name)
        champion_map[champion['name'].lower()] = (champion_id, champion_name)
        champion_map[champion['title'].lower()] = (champion_id, champion_name)
    champion1_id, champion1_name = champion_map[champion1]
    champion2_id, champion2_name = champion_map[champion2]
    champion3_id, champion3_name = champion_map[champion3]
    champion4_id, champion4_name = champion_map[champion4]
    champion5_id, champion5_name = champion_map[champion5]

    # lookup all summoners in this match by their name
    summoners = api.summoner_by_name(summoner1, summoner2, summoner3, summoner4, summoner5)
    for summoner in (summoner1, summoner2, summoner3, summoner4, summoner5):
        # raise an understandable error if a summoner name was mistyped
        assert summoner in summoners, 'Could not find summoner %r' % summoner
    summoner1_id = summoners[summoner1]['id']
    summoner2_id = summoners[summoner2]['id']
    summoner3_id = summoners[summoner3]['id']
    summoner4_id = summoners[summoner4]['id']
    summoner5_id = summoners[summoner5]['id']
    summoner1_name = summoners[summoner1]['name']
    summoner2_name = summoners[summoner2]['name']
    summoner3_name = summoners[summoner3]['name']
    summoner4_name = summoners[summoner4]['name']
    summoner5_name = summoners[summoner5]['name']

    winrate1 = 100 * api.summoner_champion_winrate(summoner1_id, champion1_id)
    winrate2 = 100 * api.summoner_champion_winrate(summoner2_id, champion2_id)
    winrate3 = 100 * api.summoner_champion_winrate(summoner3_id, champion3_id)
    winrate4 = 100 * api.summoner_champion_winrate(summoner4_id, champion4_id)
    winrate5 = 100 * api.summoner_champion_winrate(summoner5_id, champion5_id)

    print('%s on %s winrate %.0f%%' % (summoner1_name, champion1_name, winrate1))
    print('%s on %s winrate %.0f%%' % (summoner2_name, champion2_name, winrate2))
    print('%s on %s winrate %.0f%%' % (summoner3_name, champion3_name, winrate3))
    print('%s on %s winrate %.0f%%' % (summoner4_name, champion4_name, winrate4))
    print('%s on %s winrate %.0f%%' % (summoner5_name, champion5_name, winrate5))

    # lastly inform the player about their odds in this match
    avg = (winrate1 + winrate2 + winrate3 + winrate4 + winrate5) / 5.0
    print('AVERAGE WINRATE %.0f%%' % avg)

if __name__ == '__main__':
    main()
