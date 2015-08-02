#!/usr/bin/env python3.4
"""Utility program to crawl all League of Legends matches.
"""

import asyncio
import cherrypy
import riot
import os
import os.path
import signal


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'


class Crawler:

    def __init__(self, api, session):
        self.api = api
        self.session = session
        self.done = {}
        self.matches = set()
        self.summoners = set()

    def status(self):
        print('Matches:', len(self.done), 'completed,', sum(self.done.values()), 'ok,', len(self.matches), 'matches,', len(self.summoners), 'summoners')

    @asyncio.coroutine
    def run(self):
        while True:
            tasks = []
            for root, dirs, files in os.walk(os.path.join(DATA_DIR, 'match')):
                for name in files:
                    match_id = int(name.split('.')[0]) # format is {match_id}.dat
                    tasks.append(self.add_match(match_id))
            yield from asyncio.wait(tasks)
            self.summoners.clear() # refresh summoner data every cycle

    @asyncio.coroutine
    def add_match(self, match_id):
        if match_id not in self.matches:
            self.status()
            self.matches.add(match_id)

            try:
                match = yield from self.api.match_async(self.session, match_id)
            except Exception as e:
                self.done[match_id] = False
                print('...', match_id, 'has error', repr(str(e)))
            else:
                self.done[match_id] = True
                for pid in match['participantIdentities']:
                    summoner_id = pid['player']['summonerId']
                    if summoner_id not in self.summoners:
                        self.summoners.add(summoner_id)
                        for match in (yield from self.api.matchlist_async(self.session, summoner_id)):
                            yield from self.add_match(match['matchId'])


if __name__ == '__main__':
    session = riot.ClientSession()
    try:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, loop.stop)
        loop.add_signal_handler(signal.SIGTERM, loop.stop)
        loop.run_until_complete(Crawler(riot.RiotAPI(cherrypy, DATA_DIR), session).run())
    finally:
        session.close()
