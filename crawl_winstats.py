#!/usr/bin/env python3.4
"""Utility program to crawl all League of Legends matches outputting
statistics about wins and losses every minute. Output is formatted
to CSV files on disk.
"""

import asyncio
import csv
import riot
import os
import os.path
import signal
import sys


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'
MIN_MATCHES = 100 # minimum number of matches to be included in output


class Crawler:

    def __init__(self, session, api):
        self.api = api
        self.session = session
        self.matches = {}
        self.summoners = set()
        self.winner_tower_stats = {}
        self.loser_tower_stats = {}
        self.winner_kill_stats = {}
        self.loser_kill_stats = {}
        self.winner_joint_stats = {}
        self.loser_joint_stats = {}

    def update_tower_stats(self, winner_inhibs, winner_towers, loser_inhibs, loser_towers):
        if winner_inhibs > 3 or loser_inhibs > 3:
            raise ValueError('%d inhibitors killed is too many' % max(winner_inhibs, loser_inhibs))
        if winner_towers > 11 or loser_towers > 11:
            raise ValueError('%d towers killed is too many' % max(winner_towers, loser_towers))
        self.winner_tower_stats.setdefault((winner_inhibs, winner_towers, loser_inhibs, loser_towers), 0)
        self.winner_tower_stats[winner_inhibs, winner_towers, loser_inhibs, loser_towers] += 1
        self.loser_tower_stats.setdefault((loser_inhibs, loser_towers, winner_inhibs, winner_towers), 0)
        self.loser_tower_stats[loser_inhibs, loser_towers, winner_inhibs, winner_towers] += 1

    def update_kill_stats(self, winner_kills, loser_kills):
        self.winner_kill_stats.setdefault((winner_kills, loser_kills), 0)
        self.winner_kill_stats[winner_kills, loser_kills] += 1
        self.loser_kill_stats.setdefault((loser_kills, winner_kills), 0)
        self.loser_kill_stats[loser_kills, winner_kills] += 1

    def update_joint_stats(self, winner_inhibs, winner_towers, winner_kills, loser_inhibs, loser_towers, loser_kills):
        self.winner_joint_stats.setdefault((winner_inhibs, winner_towers, winner_kills, loser_inhibs, loser_towers, loser_kills), 0)
        self.winner_joint_stats[winner_inhibs, winner_towers, winner_kills, loser_inhibs, loser_towers, loser_kills] += 1
        self.loser_joint_stats.setdefault((loser_inhibs, loser_towers, loser_kills, winner_inhibs, winner_towers, winner_kills), 0)
        self.loser_joint_stats[loser_inhibs, loser_towers, loser_kills, winner_inhibs, winner_towers, winner_kills] += 1

    def collect_stats(self, match):
        winner_towers = 0
        winner_bot_inhib = False
        winner_mid_inhib = False
        winner_top_inhib = False
        loser_towers = 0
        loser_bot_inhib = False
        loser_mid_inhib = False
        loser_top_inhib = False

        winner_kills = 0
        loser_kills = 0

        winner_teams = {}
        for team in match['teams']:
            winner_teams[team['teamId']] = team['winner']

        participant_teams = {}
        for participant in match['participants']:
            participant_teams[participant['participantId']] = participant['teamId']

        last_timestamp = -1
        timeline = match.get('timeline')
        if timeline:
            self.update_tower_stats(0, 0, 0, 0)
            self.update_kill_stats(0, 0)
            self.update_joint_stats(0, 0, 0, 0, 0, 0)
            for frame in timeline['frames']:
                for event in frame.get('events', []):
                    timestamp = event['timestamp']
                    if timestamp < last_timestamp:
                        raise ValueError('Event out of sequence')
                    last_timestamp = timestamp

                    if event['eventType'] == 'BUILDING_KILL':
                        skip = False
                        team_id = event['teamId']
                        lane_type = event['laneType']
                        building_type = event['buildingType']
                        tower_type = event['towerType']

                        if building_type == 'INHIBITOR_BUILDING':
                            if tower_type != 'UNDEFINED_TURRET':
                                raise ValueError('Unkown event %r' % event)
                            if winner_teams[team_id] and lane_type == 'BOT_LANE':
                                loser_bot_inhib = True
                            elif winner_teams[team_id] and lane_type == 'MID_LANE':
                                loser_mid_inhib = True
                            elif winner_teams[team_id] and lane_type == 'TOP_LANE':
                                loser_top_inhib = True
                            elif lane_type == 'BOT_LANE':
                                winner_bot_inhib = True
                            elif lane_type == 'MID_LANE':
                                winner_mid_inhib = True
                            elif lane_type == 'TOP_LANE':
                                winner_top_inhib = True
                            else:
                                raise ValueError('Unknown event %r' % event)

                        elif building_type == 'TOWER_BUILDING':
                            # TODO: USE TOWER INFO
                            if tower_type == 'BASE_TURRET':
                                pass
                            elif tower_type == 'INNER_TURRET':
                                pass
                            elif tower_type == 'NEXUS_TURRET':
                                pass
                            elif tower_type == 'OUTER_TURRET':
                                pass
                            if tower_type != 'FOUNTAIN_TURRET':
                                if winner_teams[team_id]:
                                    loser_towers += 1
                                else:
                                    winner_towers += 1

                        else:
                            raise ValueError('Unknown building %r' % building_type)

                        self.update_tower_stats(sum([winner_bot_inhib, winner_mid_inhib, winner_top_inhib]), winner_towers,
                            sum([loser_bot_inhib, loser_mid_inhib, loser_top_inhib]), loser_towers)
                        self.update_joint_stats(
                            sum([winner_bot_inhib, winner_mid_inhib, winner_top_inhib]), winner_towers, winner_kills,
                            sum([loser_bot_inhib, loser_mid_inhib, loser_top_inhib]), loser_towers, loser_kills)

                    elif event['eventType'] == 'CHAMPION_KILL':
                        killer_id = event['killerId']
                        victim_id = event['victimId']

                        if killer_id and victim_id: # id 0 indicicates monster or minion
                            if winner_teams[participant_teams[killer_id]]:
                                winner_kills += 1
                            else:
                                loser_kills += 1

                        self.update_kill_stats(winner_kills, loser_kills)
                        self.update_joint_stats(
                            sum([winner_bot_inhib, winner_mid_inhib, winner_top_inhib]), winner_towers, winner_kills,
                            sum([loser_bot_inhib, loser_mid_inhib, loser_top_inhib]), loser_towers, loser_kills)

                    elif event['eventType'] == 'ELITE_MONSTER_KILL':
                        #print(event.keys())
                        pass

    @asyncio.coroutine
    def output(self):
        while True:
            print('matches:', len(self.matches), 'observed,', sum(self.matches.values()), 'ok, by', len(self.summoners), 'summoners')

            with open('tower_stats.csv', 'w', newline='') as f:
                writer = csv.writer(f)
                # tower stats
                for key in set(self.winner_tower_stats.keys()).union(set(self.loser_tower_stats.keys())):
                    wins = self.winner_tower_stats.get(key, 0)
                    losses = self.loser_tower_stats.get(key, 0)
                    us_inhibs, us_towers, them_inhibs, them_towers = key
                    if (wins + losses) >= MIN_MATCHES:
                        writer.writerow((wins, losses, us_inhibs, us_towers, them_inhibs, them_towers))

            with open('kill_stats.csv', 'w', newline='') as f:
                writer = csv.writer(f)
                # kill stats
                for key in set(self.winner_kill_stats.keys()).union(set(self.loser_kill_stats.keys())):
                    wins = self.winner_kill_stats.get(key, 0)
                    losses = self.loser_kill_stats.get(key, 0)
                    us_kills, them_kills = key
                    if (wins + losses) >= MIN_MATCHES:
                        writer.writerow((wins, losses, us_kills, them_kills))

            with open('joint_stats.csv', 'w', newline='') as f:
                writer = csv.writer(f)
                # joint tower and kill stats
                for key in set(self.winner_joint_stats.keys()).union(set(self.loser_joint_stats.keys())):
                    wins = self.winner_joint_stats.get(key, 0)
                    losses = self.loser_joint_stats.get(key, 0)
                    us_inhibs, us_towers, us_kills, them_inhibs, them_towers, them_kills = key
                    if (wins + losses) >= MIN_MATCHES:
                        writer.writerow((wins, losses, us_inhibs, us_towers, us_kills, them_inhibs, them_towers, them_kills))

            yield from asyncio.sleep(60)

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
                match = yield from self.api.match_timeline_nocache_async(self.session, match_id)
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
