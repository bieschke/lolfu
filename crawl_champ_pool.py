#!/usr/bin/env python3.4
"""Utility program to crawl all League of Legends matches outputting
statistics about matchup wins and losses every minute. Output is formatted
to a CSV file on disk.
"""

import asyncio
import csv
import riot
import os
import os.path
import signal
import sys


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'


class Crawler:

    def __init__(self, session, api):
        self.api = api
        self.session = session
        self.matches = {}
        self.summoners = set()
        self.winner_stats = {}
        self.loser_stats = {}

    def update_stats(self, winner_champion_id, loser_champion_id):
        self.winner_stats.setdefault((winner_champion_id, loser_champion_id), 0)
        self.winner_stats[winner_champion_id, loser_champion_id] += 1
        self.loser_stats.setdefault((loser_champion_id, winner_champion_id), 0)
        self.loser_stats[loser_champion_id, winner_champion_id] += 1

    def collect_stats(self, match):
        match_id = match['matchId']

        # determine the winning team
        winner_team_id = None
        for team in match['teams']:
            if team['winner']:
                winner_team_id = team['teamId']
        if winner_team_id is None:
            raise ValueError('Could not determine winning team for match %d' % match_id)

        # bucket winners and losers
        winners = []
        losers = []
        for participant in match['participants']:
            champion_id = participant['championId']
            if winner_team_id == participant['teamId']:
                winners.append(champion_id)
            else:
                losers.append(champion_id)
        if not winners or not losers:
            raise ValueError('Could not determine winners and losers for match %d' % match_id)

        # update stats on all champion matchups
        for w in winners:
            for l in losers:
                self.update_stats(w, l)

    @asyncio.coroutine
    def output(self):
        while True:
            yield from asyncio.sleep(60)
            matchups = set(self.winner_stats.keys()).union(set(self.loser_stats.keys()))
            print(len(self.matches), 'matches,', sum(self.matches.values()), 'ok, by', len(self.summoners), 'summoners,', len(matchups), 'matchups')
            with open('matchup_stats.csv', 'w', newline='') as f:
                writer = csv.writer(f)
                for key in matchups:
                    wins = self.winner_stats.get(key, 0)
                    losses = self.loser_stats.get(key, 0)
                    champion_1_id, champion_2_id = key
                    writer.writerow((champion_1_id, champion_2_id, wins, losses))

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
                match = yield from self.api.match_nocache_async(self.session, match_id)
            except Exception as e:
                print('...', match_id, 'has error', repr(str(e)), file=sys.stderr)
            else:
                if match is not None:
                    self.collect_stats(match)
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
        crawler = Crawler(session, riot.RiotAPI(None, DATA_DIR))
        loop.create_task(crawler.output())
        loop.create_task(crawler.run())
        loop.run_forever()
    finally:
        session.close()
