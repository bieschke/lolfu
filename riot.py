#!/usr/bin/env python3.4
"""Riot LOL API module.

This module is a lightweight Python wrapper around Riot's League of Legends
developer API. Results are all returned as JSON objects.

Developer API documentation can be found here:
https://developer.riotgames.com/api/methods
"""

import configparser
import functools
import os
import os.path
import requests
import sys
import time

CURRENT_SEASON = 'SEASON2015'
CURRENT_VERSION = '5.13'

# Riot's lanes
RIOT_TOP = 'TOP'
RIOT_JUNGLE = 'JUNGLE'
RIOT_MIDDLE = 'MIDDLE'
RIOT_BOT = 'BOTTOM'
RIOT_LANES = (RIOT_TOP, RIOT_JUNGLE, RIOT_MIDDLE, RIOT_BOT)

# Riot's roles
RIOT_NONE = 'NONE'
RIOT_SOLO = 'SOLO'
RIOT_DUO = 'DUO'
RIOT_DUO_CARRY = 'DUO_CARRY'
RIOT_DUO_SUPPORT = 'DUO_SUPPORT'
RIOT_ROLES = (RIOT_NONE, RIOT_SOLO, RIOT_DUO, RIOT_DUO_CARRY, RIOT_DUO_SUPPORT)

# Non-Riot sanctioned positions
TOP = 'TOP'
JUNGLE = 'JUNGLE'
MID = 'MID'
ADC = 'ADC'
SUPPORT = 'SUPPORT'
POSITIONS = (TOP, JUNGLE, MID, ADC, SUPPORT)


def position(lane, role, champion_id):
    """Return the position for the given lane and role."""
    if lane == RIOT_TOP and role == RIOT_SOLO:
        return TOP
    elif lane == RIOT_JUNGLE and role == RIOT_NONE:
        return JUNGLE
    elif lane == RIOT_MIDDLE and role == RIOT_SOLO:
        return MID
    elif lane == RIOT_BOT and role == RIOT_DUO_CARRY:
        return ADC
    elif lane == RIOT_BOT and role == RIOT_DUO_SUPPORT:
        return SUPPORT
    return None


class RiotAPI:

    base_url = 'https://na.api.pvp.net'
    last_call = time.time()

    def __init__(self, **kw):
        """Read configuration options from riot.cfg if they are not specified
        explicitly as a keyword argument in this constructor.
        """
        cfg = configparser.SafeConfigParser()
        cfg.read(os.path.dirname(os.path.abspath(__file__)) + os.sep + 'riot.cfg')
        self.api_key = cfg.get('riot', 'api_key', vars=kw)

    def call(self, path, **params):
        """Execute a remote API call and return the JSON results."""
        params['api_key'] = self.api_key

        retry_seconds = 60
        while True:

            start = time.time()
            response = requests.get(self.base_url + path, params=params)
            end = time.time()
            #print('[%.0fms] %d %s' % (1000.0 * (end - start), response.status_code, path), file=sys.stderr)

            # https://developer.riotgames.com/docs/response-codes
            # https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
            if response.status_code == 429:
                # retry after we're within our rate limit
                time.sleep(float(response.headers['Retry-After']) + 1)
                continue
            elif response.status_code in (500, 502, 503, 504):
                # retry when the Riot API is having (hopefully temporary) difficulties
                time.sleep(retry_seconds)
                retry_seconds *= 2
                continue
            response.raise_for_status()
            break

        return response.json()

    @functools.lru_cache()
    def champion_image(self, champion_id):
        """Return the image filename for the given champion."""
        if champion_id == 223:
            return "TahmKench.png" # FIXME
        for champion in self.champions()['data'].values():
            if champion_id == champion['id']:
                return champion['image']['full']
        return None

    @functools.lru_cache()
    def champion_name(self, champion_id):
        """Return the name of the champion associated with the given champion ID."""
        if champion_id == 223:
            return 'Tahm Kench' # FIXME
        return self.call('/api/lol/static-data/na/v1.2/champion/%d' % int(champion_id))['name']

    @functools.lru_cache()
    def champions(self):
        """Return all champions."""
        return self.call('/api/lol/static-data/na/v1.2/champion', champData='image')

    @functools.lru_cache()
    def tier_division(self, summoner_id):
        """Return the (tier, division) of the given summoner."""
        try:
            return self.tiers_divisions([summoner_id])[summoner_id]
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None, None
            raise

    def tiers_divisions(self, summoner_ids):
        """Return the (tier, division) for the given summoners keyed by summoner_id."""
        string_ids = [str(summoner_id) for summoner_id in summoner_ids]
        response = self.call('/api/lol/na/v2.5/league/by-summoner/%s/entry' % ','.join(string_ids))
        result = {}
        for summoner_id, string_id in zip(summoner_ids, string_ids):
            for league in response.get(string_id, []):
                if league['queue'] == 'RANKED_SOLO_5x5':
                    for entry in league['entries']:
                        if entry['playerOrTeamId'] == string_id:
                            result[summoner_id] = (league['tier'].capitalize(), entry['division'])
        return result

    @functools.lru_cache()
    def match(self, match_id):
        """Return the requested match."""
        return self.call('/api/lol/na/v2.2/match/%d' % int(match_id))

    def matchhistory(self, summoner_id, begin_index=0, end_index=15):
        """Return the summoner's ranked 5s match history."""
        return self.call('/api/lol/na/v2.2/matchhistory/%s' % summoner_id,
            rankedQueues='RANKED_SOLO_5x5', begindIndex=begin_index, endIndex=end_index)

    @functools.lru_cache()
    def summoner_by_name(self, name):
        """Return the summoner having the given name."""
        for summoner in self.call('/api/lol/na/v1.4/summoner/by-name/%s' % name).values():
            return summoner['id'], summoner['name']
        return None, None

    @functools.lru_cache()
    def summoner_stats(self, summoner_id):
        """Return statistics for the given summoner."""
        return self.call('/api/lol/na/v1.3/stats/by-summoner/%d/ranked' % int(summoner_id))

    @functools.lru_cache()
    def summoner_champion_stats(self, summoner_id, champion_id):
        """Return stats for the given summoner."""
        for champion in self.summoner_stats(summoner_id).get('champions', []):
            if champion_id == champion['id']:
                return champion['stats']
        return None
