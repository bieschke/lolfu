#!/usr/bin/env python
"""Riot LOL API module.

This module is a lightweight Python wrapper around Riot's League of Legends
developer API. Results are all returned as JSON objects.

Developer API documentation can be found here:
https://developer.riotgames.com/api/methods
"""

import ConfigParser
import json
import time
import urllib
import urllib2

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
    elif lane == RIOT_BOT and role == RIOT_DUO:
        adc_champions = (22,51,42,119,81,104,222,429,96,236,21,133,15,18,29,6,110,67)
        if champion_id in adc_champions:
            return ADC
        return SUPPORT
    raise ValueError('Undefined position: lane=%r role=%r champion_id=%r' % (lane, role, champion_id))


class RiotAPI(object):

    base_url = 'https://na.api.pvp.net'
    requests_per_second = 500.0 / 600.0  # 500 requests every 10 minutes
    last_call = time.time()

    def __init__(self, **kw):
        """Read configuration options from riot.cfg if they are not specified
        explicitly as a keyword argument in this constructor.
        """
        cfg = ConfigParser.SafeConfigParser()
        cfg.read('riot.cfg')
        self.dev_key = cfg.get('riot', 'dev_key', vars=kw)
        self.bootstrap_summoner_ids = set(cfg.get('riot', 'bootstrap_summoner_ids', vars=kw).split(','))

    def call(self, path, **kw):
        """Execute a remote API call and return the JSON results."""
        next_call = RiotAPI.last_call + (1 / self.requests_per_second)
        delta = next_call - time.time()
        if delta > 0:
            time.sleep(delta)
        kw['api_key'] = self.dev_key
        url = self.base_url + path + '?' + urllib.urlencode(kw)
        while True:
            retry_seconds = 60
            try:
                #print 'Calling Riot @ %s' % url
                request = urllib2.urlopen(url)
            except urllib2.HTTPError as e:
                # https://developer.riotgames.com/docs/response-codes
                if e.code == 429:
                    # retry after we're within our rate limit
                    time.sleep(float(e.headers['Retry-After']) + 1)
                    continue
                elif e.code in (500, 503):
                    # retry when the Riot API is having (hopefully temporary) difficulties
                    time.sleep(retry_seconds)
                    retry_seconds *= 2
                    continue
                else:
                    raise
            break
        data = json.load(request)
        RiotAPI.last_call = time.time()
        return data

    def champion_name(self, champion_id):
        """Return the name of the champion associated with the given champion ID."""
        return self.call('/api/lol/static-data/na/v1.2/champion/%d' % int(champion_id))['name']

    def champions(self):
        """Return all champions."""
        return self.call('/api/lol/static-data/na/v1.2/champion')

    def match(self, match_id):
        """Return the requested match."""
        return self.call('/api/lol/na/v2.2/match/%d' % int(match_id))

    def matchhistory(self, summoner_id, begin_index=0, end_index=15):
        """Return the summoner's ranked 5s match history."""
        return self.call('/api/lol/na/v2.2/matchhistory/%s' % summoner_id,
            rankedQueues='RANKED_SOLO_5x5', begindIndex=begin_index, endIndex=end_index)

    def summoner_by_name(self, *names):
        """Return the summoner having the given name(s) as CSV."""
        stripped = [''.join(n.lower().split()) for n in names]
        joined = ','.join(stripped)
        return self.call('/api/lol/na/v1.4/summoner/by-name/%s' % joined)

    def summoner_stats(self, summoner_id):
        """Return statistics for the given summoner."""
        return self.call('/api/lol/na/v1.3/stats/by-summoner/%d/ranked' % int(summoner_id))
