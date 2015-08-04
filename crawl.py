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

    def __init__(self, session, api):
        self.api = api
        self.session = session
        self.matches = {}
        self.summoners = set()

    @asyncio.coroutine
    def status(self):
        while True:
            print('Matches:', len(self.matches), 'completed,', sum(self.matches.values()), 'ok,', len(self.summoners), 'summoners')
            yield from asyncio.sleep(1)

    @asyncio.coroutine
    def run(self):
        chunk = 100
        tasks = []

        i = 0
        for root, dirs, files in os.walk(os.path.join(DATA_DIR, 'match')):
            for name in files:
                i += 1
                match_id = int(name.split('.')[0]) # format is {match_id}.dat
                tasks.append(self.add_match(match_id))
                if not i % chunk:
                    yield from asyncio.wait(tasks)
                    tasks.clear()
        yield from asyncio.wait(tasks)
        tasks.clear()

        while self.summoners:
            summoners = list(self.summoners)
            while summoners:
                yield from asyncio.wait([self.add_summoner(s) for s in summoners[:chunk]])
                del summoners[:chunk]

    @asyncio.coroutine
    def add_match(self, match_id):
        if match_id not in self.matches:
            self.matches[match_id] = False
            try:
                match = yield from self.api.match_async(self.session, match_id)
            except Exception as e:
                print('...', match_id, 'has error', repr(str(e)))
            else:
                if match is not None:
                    for pid in match['participantIdentities']:
                        summoner_id = pid['player']['summonerId']
                        self.summoners.add(summoner_id)
                    self.matches[match_id] = True

    @asyncio.coroutine
    def add_summoner(self, summoner_id):
        for match in (yield from self.api.matchlist_async(self.session, summoner_id)):
            yield from self.add_match(match['matchId'])


if __name__ == '__main__':
    session = riot.ClientSession()
    try:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, loop.stop)
        loop.add_signal_handler(signal.SIGTERM, loop.stop)
        crawler = Crawler(session, riot.RiotAPI(cherrypy, DATA_DIR))
        loop.create_task(crawler.status())
        loop.create_task(crawler.run())
        loop.run_forever()
    finally:
        session.close()
