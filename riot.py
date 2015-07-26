#!/usr/bin/env python3.4
"""Riot LOL API module.

This module is a lightweight Python wrapper around Riot's League of Legends
developer API. Results are all returned as JSON objects.

Developer API documentation can be found here:
https://developer.riotgames.com/api/methods
"""

import cherrypy
import configparser
import functools
import json
import operator
import os
import os.path
import requests
import sys
import threading
import time
import queue

CURRENT_SEASON = 'SEASON2015'
CURRENT_VERSION = '5.14'

SOLOQUEUE = 'RANKED_SOLO_5x5'

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

    def __init__(self, cache_dir):
        cfg = configparser.SafeConfigParser()
        cfg.read(os.path.dirname(os.path.abspath(__file__)) + os.sep + 'riot.cfg')
        self.api_key = cfg.get('riot', 'api_key')
        self.cache_dir = cache_dir

    def call(self, path, cache_to_file=False, **params):
        """Execute a remote API call and return the JSON results."""
        params['api_key'] = self.api_key

        if cache_to_file:
            try:
                with open(cache_to_file, 'r') as f:
                    return json.load(f)
            except OSError:
                pass # cache file does not exist

        retry_seconds = 1
        while True:

            start = time.time()
            response = requests.get(self.base_url + path, params=params)
            end = time.time()
            cherrypy.log('[%.0fms] %d %s' % (1000.0 * (end - start), response.status_code, path))

            # https://developer.riotgames.com/docs/response-codes
            # https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
            if response.status_code == 404:
                # API returns 404 when the requested entity doesn't exist
                return None
            elif response.status_code == 429:
                # retry after we're within our rate limit
                time.sleep(float(response.headers.get('Retry-After', retry_seconds)))
                retry_seconds *= 2
                continue
            elif response.status_code in (500, 502, 503, 504):
                # retry when the Riot API is having (hopefully temporary) difficulties
                time.sleep(retry_seconds)
                retry_seconds *= 2
                continue
            response.raise_for_status()
            break

        result = response.json()

        if cache_to_file:
            os.makedirs(os.path.dirname(cache_to_file), exist_ok=True)
            with open(cache_to_file, 'x') as f:
                json.dump(result, f)

        return result

    def champion_image(self, champion_id):
        """Return the image filename for the given champion."""
        return self.champions()['data'][str(champion_id)]['image']['full']

    def champion_name(self, champion_id):
        """Return the name of the champion associated with the given champion ID."""
        return self.champions()['data'][str(champion_id)]['name']

    @functools.lru_cache(1)
    def champions(self):
        """Return all champions."""
        return self.call('/api/lol/static-data/na/v1.2/champion', champData='image', dataById='true')

    @functools.lru_cache()
    def match(self, match_id):
        """Return the requested match."""
        cache_file = os.path.join(self.cache_dir, 'match',
            str(match_id)[-1], str(match_id)[-2], str(match_id)[-3], '%d.dat' % match_id)
        return self.call('/api/lol/na/v2.2/match/%d' % match_id, cache_to_file=cache_file)

    def matchlist(self, summoner_id):
        """Return the match list for the given summoner."""
        return self.call('/api/lol/na/v2.2/matchlist/by-summoner/%s' % summoner_id,
            rankedQueues=SOLOQUEUE, seasons=CURRENT_SEASON).get('matches', [])

    @functools.lru_cache()
    def summoner_by_name(self, name):
        """Return the summoner having the given name."""
        summoner = self.call('/api/lol/na/v1.4/summoner/by-name/%s' % name)
        if summoner:
            for dto in summoner.values():
                summoner_id = dto['id']
                name = dto['name']
                tier = self.tier(summoner_id)
                return Summoner(summoner_id, name, tier)
        return None

    @functools.lru_cache()
    def tier(self, summoner_id):
        """Return the tier of the given summoner."""

        cache_file = os.path.join(self.cache_dir, 'tier',
            str(summoner_id)[-1], str(summoner_id)[-2], str(summoner_id)[-3], '%d.dat' % summoner_id)
        response = self.call('/api/lol/na/v2.5/league/by-summoner/%s/entry' % summoner_id, cache_to_file=cache_file)

        if response:
            for league in response.get(str(summoner_id), []):
                if league['queue'] == SOLOQUEUE:
                    return league['tier'].capitalize()
        return None

    @functools.lru_cache()
    def victory(self, match_id, summoner_id):
        """Return true iff the given summoner won the given match.
        
        Returns None if the summoner did not play in the given match or if the given match
        does not exist.
        """
        match = self.match(match_id)

        if match:

            # map participants to summoners
            summoner_ids = {}
            for pid in match['participantIdentities']:
                summoner_ids[pid['participantId']] = pid['player']['summonerId']

            for participant in match['participants']:
                if summoner_id == summoner_ids[participant['participantId']]:
                    return participant['stats']['winner']

        return None


class Summoner:

    def __init__(self, summoner_id, name, tier):
        self.summoner_id = summoner_id
        self.name = name
        self.tier = tier
