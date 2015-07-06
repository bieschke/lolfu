#!/usr/bin/env python3.4
"""Riot LOL API module.

This module is a lightweight Python wrapper around Riot's League of Legends
developer API. Results are all returned as JSON objects.

Developer API documentation can be found here:
https://developer.riotgames.com/api/methods
"""

import configparser
import csv
import functools
import operator
import os.path
import requests
import sys
import time

CURRENT_SEASON = 'SEASON2015'

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

CHAMPION_OVERALL = 0 # magic id used to indicate all champions for a summoner

RIOT_CHAMPION_IDS = '{62,24,35,19,76,143,63,33,42,201,34,23,21,53,83,101,15,92,61,41,54,78,30,126,20,48,113,104,25,150,99,102,58,114,222,429,105,38,37,39,112,69,57,412,10,120,121,2,115,134,36,43,1,84,89,157,85,107,13,98,154,80,50,432,14,67,75,4,31,77,236,106,51,122,56,26,268,68,72,17,6,32,3,74,22,161,27,110,29,86,131,11,60,12,55,245,82,96,266,119,9,91,5,64,44,90,127,18,421,8,59,267,16,45,40,111,28,79,238,254,117,103,133,7,81}'

RIOT_CHAMPION_KEYS = '{MonkeyKing,Jax,Shaco,Warwick,Nidalee,Zyra,Brand,Rammus,Corki,Braum,Anivia,Tryndamere,MissFortune,Blitzcrank,Yorick,Xerath,Sivir,Riven,Orianna,Gangplank,Malphite,Poppy,Karthus,Jayce,Nunu,Trundle,Sejuani,Graves,Morgana,Gnar,Lux,Shyvana,Renekton,Fiora,Jinx,Kalista,Fizz,Kassadin,Sona,Irelia,Viktor,Cassiopeia,Maokai,Thresh,Kayle,Hecarim,Khazix,Olaf,Ziggs,Syndra,DrMundo,Karma,Annie,Akali,Leona,Yasuo,Kennen,Rengar,Ryze,Shen,Zac,Pantheon,Swain,Bard,Sion,Vayne,Nasus,TwistedFate,Chogath,Udyr,Lucian,Volibear,Caitlyn,Darius,Nocturne,Zilean,Azir,Rumble,Skarner,Teemo,Urgot,Amumu,Galio,Heimerdinger,Ashe,Velkoz,Singed,Varus,Twitch,Garen,Diana,MasterYi,Elise,Alistar,Katarina,Ekko,Mordekaiser,KogMaw,Aatrox,Draven,FiddleSticks,Talon,XinZhao,LeeSin,Taric,Malzahar,Lissandra,Tristana,RekSai,Vladimir,JarvanIV,Nami,Soraka,Veigar,Janna,Nautilus,Evelynn,Gragas,Zed,Vi,Lulu,Ahri,Quinn,Leblanc,Ezreal}'


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


class RiotAPI(object):

    base_url = 'https://na.api.pvp.net'
    last_call = time.time()

    def __init__(self, **kw):
        """Read configuration options from riot.cfg if they are not specified
        explicitly as a keyword argument in this constructor.
        """
        cfg = configparser.SafeConfigParser()
        cfg.read(os.path.dirname(os.path.abspath(__file__)) + '/riot.cfg')
        self.api_key = cfg.get('riot', 'api_key', vars=kw)
        self.bootstrap_summoner_ids = set(cfg.get('riot', 'bootstrap_summoner_ids', vars=kw).split(','))
        self.requests_per_second = cfg.getfloat('riot', 'requests_per_10min', vars=kw) / 600.0
        self.winrate_file = cfg.get('riot', 'winrate_file', vars=kw)
        self.load_winrate_file()

    def load_winrate_file(self):
        winrates = {}
        with open(self.winrate_file) as f:
            for row in csv.reader(f):
                tier, position, champion_id, winrate = row
                if '?' not in row:
                    winrates.setdefault(tier, {}).setdefault(position, {})[int(champion_id)] = float(winrate)
        self.winrates = winrates

    def call(self, path, throttle=True, **params):
        """Execute a remote API call and return the JSON results."""
        params['api_key'] = self.api_key

        retry_seconds = 60
        while True:

            next_call = self.last_call + (1 / self.requests_per_second)
            delta = next_call - time.time()
            if delta > 0 and throttle:
                time.sleep(delta)

            start = time.time()
            response = requests.get(self.base_url + path, params=params)
            end = time.time()
            print('[%.0fms] %s' % (1000.0 * (end - start), path), file=sys.stderr)
            if throttle:
                self.last_call = time.time()

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
        for champion in self.champions()['data'].values():
            if champion_id == champion['id']:
                return champion['image']['full']
        return None

    @functools.lru_cache()
    def champion_key(self, champion_id):
        """Return the text key for the given champion."""
        for champion in self.champions()['data'].values():
            if champion_id == champion['id']:
                return champion['key']
        return None

    @functools.lru_cache()
    def champion_name(self, champion_id):
        """Return the name of the champion associated with the given champion ID."""
        return self.call('/api/lol/static-data/na/v1.2/champion/%d' % int(champion_id), throttle=False)['name']

    @functools.lru_cache()
    def champions(self):
        """Return all champions."""
        return self.call('/api/lol/static-data/na/v1.2/champion', champData='image', throttle=False)

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
        """Return the summoner having the given name(s) as CSV."""
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

    def summoner_champion_summary(self, summoner_id, tier):
        """Return a summary of how a summoner performs on all champions."""
        wins = {}
        losses = {}

        abort = False
        begin_index = 0
        step = 15 # maximum allowable through Riot API
        while not abort:

            # walk through summoner's match history STEP matches at a time
            end_index = begin_index + step
            matches = self.matchhistory(summoner_id, begin_index, end_index).get('matches', [])
            if not matches:
                break
            begin_index += step

            # process each match
            for match in matches:
                match_id = match['matchId']
                if match['season'] != CURRENT_SEASON:
                    abort = True
                    break

                if len(match['participants']) != 1:
                    raise ValueError('Expected exactly one participant')
                participant = match['participants'][0]

                champion_id = participant['championId']
                timeline = participant['timeline']
                lane = timeline['lane']
                role = timeline['role']
                victory = participant['stats']['winner']

                p = position(lane, role, champion_id)
                if p is None:
                    continue # skip matches where we can't determine position

                if victory:
                    wins.setdefault(p, {}).setdefault(champion_id, 0)
                    wins[p][champion_id] += 1
                else:
                    losses.setdefault(p, {}).setdefault(champion_id, 0)
                    losses[p][champion_id] += 1

        # assemble results grouped by position and sorted by strength
        results = {}
        for p in POSITIONS:
            tier_winrates = self.winrates.get(tier, {}).get(p.lower(), {})
            result = []
            cw = wins.get(p, {})
            cl = losses.get(p, {})
            champions = set(tier_winrates.keys()).union(cw.keys()).union(cl.keys())
            for champion_id in champions:
                w = cw.get(champion_id, 0)
                l = cl.get(champion_id, 0)
                r = None
                if (w + l) > 0:
                    r = w / float(w + l)
                t = tier_winrates.get(champion_id, 0.5) # assume 50% winrate with no data
                k = 10.0 # smoothing factor, how quickly or slowly expected winrate moves
                e = ((k * t) + w) / (k + w + l)
                result.append((champion_id, w, l, r, t, e))
            results[p] = sorted(result, key=operator.itemgetter(5), reverse=True)
        return results
