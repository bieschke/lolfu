#!/usr/bin/env python3.4

import argparse
import os
import os.path
import riot
import threading
import queue


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'
MATCH_FILE = DATA_DIR + os.sep + 'match.csv'


class MatchThread(threading.Thread):

    def __init__(self, match_queue, start_id):
        threading.Thread.__init__(self, daemon=True)
        self.match_queue = match_queue
        self.next_id = start_id

    def run(self):
        while True:
            self.match_queue.put(self.next_id)
            self.next_id += 1


class PrintThread(threading.Thread):

    def __init__(self, print_queue, outfile):
        threading.Thread.__init__(self, daemon=True)
        self.print_queue = print_queue
        self.outfile = outfile

    def run(self):
        while True:
            line = self.print_queue.get()
            print(line, file=self.outfile)
            self.print_queue.task_done()


class ApiCallThread(threading.Thread):

    def __init__(self, api, match_queue, print_queue):
        threading.Thread.__init__(self, daemon=True)
        self.api = api
        self.match_queue = match_queue
        self.print_queue = print_queue

    def run(self):
        while True:
            match_id = self.match_queue.get()
            self.work(match_id)
            self.match_queue.task_done()

    def work(self, match_id):
        match = self.api.match(match_id)
        if not match:
            return
        if match['queueType'] != 'RANKED_SOLO_5x5':
            return

        # create a mapping of participant ids to summoner ids
        summoner_ids = {}
        for identity in match['participantIdentities']:
            participant_id = identity['participantId']
            summoner_id = int(identity['player']['summonerId'])
            summoner_ids[participant_id] = summoner_id

        # create a mapping of summoner ids to tier and divisions
        tier_divisions = self.api.tiers_divisions(summoner_ids.values())
        if not tier_divisions:
            tier_divisions = {}

        # collect data for each participant
        winners = {}
        losers = {}
        for participant in match['participants']:
            participant_id = participant['participantId']
            summoner_id = int(summoner_ids[participant_id])
            champion_id = int(participant['championId'])
            stats = participant['stats']
            timeline = participant['timeline']
            lane = timeline['lane']
            role = timeline['role']
            tier = tier_divisions.get(summoner_id, ('?', '?'))[0]
            position = riot.position(lane, role, champion_id)
            if stats['winner']:
                winners[position] = (summoner_id, champion_id, tier)
            else:
                losers[position] = (summoner_id, champion_id, tier)

        # cheesy CSV formatting
        output = [match_id, match['matchVersion'], match['matchCreation']]
        for participants in (winners, losers):
            # align participants ordering with position ordering
            for position in riot.POSITIONS:
                output.extend(participants.get(position, ('?', '?', '?')))
        self.print_queue.put(','.join([str(i) for i in output]))


def main(start_id, thread_count):
    api = riot.RiotAPI()

    match_queue = queue.Queue(thread_count * 10)
    print_queue = queue.Queue()

    with open(MATCH_FILE, 'a') as f:
        PrintThread(print_queue, f).start()
        for i in range(thread_count):
            ApiCallThread(api, match_queue, print_queue).start()
        MatchThread(match_queue, start_id).start()

        match_queue.join()
        print_queue.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-id', type=int, default=0, help='What match id should we start on?')
    parser.add_argument('--thread-count', type=int, default=100, help='How many API calling threads should we run?')
    args = parser.parse_args()
    main(args.start_id, args.thread_count)
