#!/usr/bin/env python

import json
import time
import urllib2

ROBO = 43669030


class RiotAPI:
    dev_key = 'ac77102b-371e-4977-a2f9-56bbf8ffbcd8'
    base_url = 'https://na.api.pvp.net'
    requests_per_second = 500.0 / 600.0  # 500 requests every 10 minutes
    last_call = 0.0

    def call(self, path):
        next_call = RiotAPI.last_call + (1 / self.requests_per_second)
        delta = next_call - time.time()
        if delta > 0:
            time.sleep(delta)
        url = self.base_url + path + '?api_key=%s' % self.dev_key
        request = urllib2.urlopen(url)
        data = json.load(request)
        RiotAPI.last_call = time.time()
        return data

    def recent_games(self, summoner_id):
        return self.call('/api/lol/na/v1.3/game/by-summoner/%d/recent' % summoner_id)
