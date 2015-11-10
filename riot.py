#!/usr/bin/env python3.4
"""Riot LOL API module.

This module is a lightweight Python wrapper around Riot's League of Legends
developer API. Results are all returned as JSON objects.

Developer API documentation can be found here:
https://developer.riotgames.com/api/methods
"""

import asyncio
import aiohttp
import cachetools
import configparser
import functools
import json
import os
import os.path
import requests
import time
import urllib.parse

CURRENT_SEASON = 'SEASON2015'

SOLOQUEUE = 'RANKED_SOLO_5x5'

# Riot's lanes
RIOT_TOP = ('TOP', )
RIOT_JUNGLE = ('JUNGLE', )
RIOT_MIDDLE = ('MID', 'MIDDLE')
RIOT_BOT = ('BOT', 'BOTTOM')

# Riot's roles
RIOT_NONE = 'NONE'
RIOT_SOLO = 'SOLO'
RIOT_DUO = 'DUO'
RIOT_DUO_CARRY = 'DUO_CARRY'
RIOT_DUO_SUPPORT = 'DUO_SUPPORT'

# Non-Riot sanctioned positions
TOP = 'TOP'
JUNGLE = 'JUNGLE'
MID = 'MID'
ADC = 'ADC'
SUPPORT = 'SUPPORT'
POSITIONS = (TOP, JUNGLE, MID, ADC, SUPPORT)


def position(lane, role):
    """Return the position for the given lane and role."""
    if lane in RIOT_TOP and role == RIOT_SOLO:
        return TOP
    elif lane in RIOT_JUNGLE and role == RIOT_NONE:
        return JUNGLE
    elif lane in RIOT_MIDDLE and role == RIOT_SOLO:
        return MID
    elif lane in RIOT_BOT and role == RIOT_DUO_CARRY:
        return ADC
    elif lane in RIOT_BOT and role == RIOT_DUO_SUPPORT:
        return SUPPORT
    return None


class RiotAPI:

    base_url = 'https://na.api.pvp.net'

    def __init__(self, logger, cache_dir):
        cfg = configparser.SafeConfigParser()
        cfg.read(os.path.dirname(os.path.abspath(__file__)) + os.sep + 'riot.cfg')
        self.api_key = cfg.get('riot', 'api_key')
        self.logger = logger
        self.cache_dir = cache_dir

    def _cache_file_check(self, cache_file):
        return os.path.exists(cache_file)

    def _cache_file_read(self, cache_file):
        if cache_file:
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except OSError:
                pass # cache file does not exist
        return None

    def _cache_file_write(self, cache_file, result):
        if cache_file and result:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            try:
                with open(cache_file, 'x') as f:
                    json.dump(result, f)
            except FileExistsError:
                pass # okay if some other process has/is already cached this

    def call(self, path, cache_file=False, **params):
        """Execute a remote API call and return the JSON results."""
        params['api_key'] = self.api_key

        result = self._cache_file_read(cache_file)
        if result:
            return result

        retry_seconds = 1
        while True:

            start = time.time()
            response = requests.get(self.base_url + path, params=params)
            end = time.time()
            if self.logger:
                self.logger.log('[%.0fms] %d %s' % (1000.0 * (end - start), response.status_code, path))

            # https://developer.riotgames.com/docs/response-codes
            # https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
            if response.status_code == 404:
                # API returns 404 when the requested entity doesn't exist
                return None
            elif response.status_code in (403, 429):
                # retry after we're within our rate limit
                # 429 is the expected "retry later" code
                # 403 is expected after we've violated too many times and have been blacklisted
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
        self._cache_file_write(cache_file, result)
        return result

    @asyncio.coroutine
    def call_async(self, session, path, cache_file=False, **params):
        params['api_key'] = self.api_key

        result = self._cache_file_read(cache_file)
        if result:
            return result

        retry_seconds = 1
        while True:
            retry_after = None
            with (yield from session.sem):
                start = time.time()
                response = yield from session.get(self.base_url + path, params=params)
                try:
                    end = time.time()
                    if self.logger:
                        self.logger.log('[%.0fms] %d %s' % (1000.0 * (end - start), response.status, path))
                    # https://developer.riotgames.com/docs/response-codes
                    # https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
                    if response.status == 404:
                        # API returns 404 when the requested entity doesn't exist
                        result = None
                        break
                    elif response.status == 429:
                        # retry after we're within our rate limit
                        retry_after = float(response.headers.get('Retry-After', retry_seconds))
                    elif response.status in (500, 502, 503, 504):
                        # retry when the Riot API is having (hopefully temporary) difficulties
                        retry_after = retry_seconds
                        retry_seconds *= 2
                    else:
                        result = yield from response.json()
                        break
                finally:
                    response.close()

            if retry_after:
                yield from asyncio.sleep(retry_after)

        self._cache_file_write(cache_file, result)
        return result

    def champion_ids(self):
        """Return all champion ids."""
        return set(int(key) for key in self.champions()['data'].keys())

    def champion_image(self, champion_id):
        """Return the image filename for the given champion."""
        return self.champions()['data'][str(champion_id)]['image']['full']

    def champion_key(self, champion_id):
        """Return the key for the given champion."""
        return self.champions()['data'][str(champion_id)]['key']

    def champion_name(self, champion_id):
        """Return the name of the champion associated with the given champion ID."""
        return self.champions()['data'][str(champion_id)]['name']

    @functools.lru_cache(1)
    def champions(self):
        """Return all champions."""
        return self.call('/api/lol/static-data/na/v1.2/champion', champData='image', dataById='true')

    def match_cache_file(self, match_id):
        return os.path.join(self.cache_dir, 'match',
            str(match_id)[-1], str(match_id)[-2], str(match_id)[-3], '%d.dat' % match_id)

    def match_path(self, match_id):
        return '/api/lol/na/v2.2/match/%d' % match_id

    @functools.lru_cache()
    def match(self, match_id):
        """Return the requested match."""
        return self.call(self.match_path(match_id), cache_file=self.match_cache_file(match_id))

    @asyncio.coroutine
    def match_async(self, session, match_id):
        """Return the requested match within a coroutine."""
        return (yield from self.call_async(session, self.match_path(match_id), cache_file=self.match_cache_file(match_id)))

    @asyncio.coroutine
    def match_nocache_async(self, session, match_id):
        """Return the requested match within a coroutine."""
        return (yield from self.call_async(session, self.match_path(match_id)))

    @asyncio.coroutine
    def match_timeline_nocache_async(self, session, match_id):
        """Return the requested match within a coroutine."""
        return (yield from self.call_async(session, self.match_path(match_id), includeTimeline='true'))

    def matchlist_path(self, summoner_id):
        return '/api/lol/na/v2.2/matchlist/by-summoner/%s' % summoner_id

    @cachetools.ttl_cache(ttl=60)
    def matchlist(self, summoner_id):
        """Return the match list for the given summoner."""
        matchlist = self.call(self.matchlist_path(summoner_id), rankedQueues=SOLOQUEUE, seasons=CURRENT_SEASON)
        if matchlist:
            return matchlist.get('matches', [])
        return []

    def matchlist_check(self, summoner_id):
        """Return the count of the number of matches by the summoner already known and total as a tuple."""
        matchlist = self.matchlist(summoner_id)
        return (sum(self._cache_file_check(self.match_cache_file(m['matchId'])) for m in matchlist), len(matchlist))

    @asyncio.coroutine
    def matchlist_async(self, session, summoner_id):
        """Return the match list for the given summoner within a coroutine."""
        matchlist = yield from self.call_async(session, self.matchlist_path(summoner_id), rankedQueues=SOLOQUEUE, seasons=CURRENT_SEASON)
        if matchlist:
            return matchlist.get('matches', [])
        return []

    @functools.lru_cache()
    def summoner_by_name(self, name):
        """Return the summoner having the given name."""
        summoner = self.call('/api/lol/na/v1.4/summoner/by-name/%s' % urllib.parse.quote(name))
        if summoner:
            for standardized_name, dto in summoner.items():
                summoner_id = dto['id']
                name = dto['name']
                return Summoner(summoner_id, name, standardized_name)
        return None


class Summoner:

    def __init__(self, summoner_id, name, standardized_name):
        self.summoner_id = summoner_id
        self.name = name
        self.standardized_name = standardized_name


class ClientSession(aiohttp.ClientSession):

    MAX_CONCURRENCY = 100

    def __init__(self):

        # lazily create the default event loop for this thread
        try:
            loop = asyncio.get_event_loop()
        except:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # some installations of Python 3.4 have a bug in asyncio that this works around
        connector = aiohttp.TCPConnector(verify_ssl=False)

        super(ClientSession, self).__init__(connector=connector)

        self.sem = asyncio.Semaphore(self.MAX_CONCURRENCY)
