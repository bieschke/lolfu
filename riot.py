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
RIOT_BOT = 'BOT'
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
MID = 'MID'
JUNGLE = 'JUNGLE'
ADC = 'ADC'
SUPPORT = 'SUPPORT'
BOT = 'BOT'
POSITIONS = (TOP, MID, JUNGLE, ADC, SUPPORT, BOT)


def position(lane, role):
    """Return the position for the given lane and role."""
    if lane == RIOT_TOP:
        return TOP
    elif lane == RIOT_JUNGLE:
        return JUNGLE
    elif lane == RIOT_MIDDLE:
        return MID
    elif lane == RIOT_BOT and role == RIOT_DUO_CARRY:
        return ADC
    elif lane == RIOT_BOT and role == RIOT_DUO_SUPPORT:
        return SUPPORT
    return BOT


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
                if e.code in (500, 503):
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

    def summoner_name(self, summoner_id):
        """Return the name of the summoner."""
        sid = str(summoner_id)
        return self.summoner_names(sid)[sid]

    def summoner_names(self, summoner_ids):
        """Return the names of all given CSV summoners."""
        return self.call('/api/lol/na/v1.4/summoner/%s/name' % summoner_ids)

    def summoner_stats(self, summoner_id):
        """Return statistics for the given summoner."""
        return self.call('/api/lol/na/v1.3/stats/by-summoner/%d/ranked' % int(summoner_id))

    def summoner_champion_winrate(self, summoner_id, champion_id):
        """Return the win rate [0,1] of the given summoner on the given champion."""
        for champion in self.summoner_stats(summoner_id).get('champions', []):
            if champion_id == champion.get('id'):
                stats = champion['stats']
                return float(stats['totalSessionsWon']) / stats['totalSessionsPlayed']
        return 0.0
