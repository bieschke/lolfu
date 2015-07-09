#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name and receive a webpage that advises them about which champions to play.

http://leagueoflegends.com
"""

import argparse
import cherrypy
import operator
import os
import os.path
import riot
import sys
import threading
import queue
from mako.lookup import TemplateLookup


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'
HTML_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'html'
STATIC_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'static'
TMP_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'tmp'


MATCH_FILE = DATA_DIR + os.sep + 'match.csv'


lookup = TemplateLookup(directories=HTML_DIR, module_directory=TMP_DIR)


class Lolfu:
    """CherryPy application that allows League of Legends summoners to lookup their
    summoner by name and receive a webpage in return that advises them what are the
    winrate optimal champions to play in each position.
    """

    def __init__(self):
        self.api = riot.RiotAPI()
        self.wins = {}
        self.losses = {}
        self.known_match_ids = set()
        self.known_summoner_ids = set()
        self.background_match_collection()

    def background_match_collection(self):
        """Launch daemon threads to collect match data."""

        # accumulate all of the ids for which we have already collected data
        with open(MATCH_FILE, 'r') as f:
            for line in f:
                row = line.strip().split(',')
                try:
                    match_id, match_version, match_creation, \
                        winner_top_summoner_id, winner_top_champion_id, winner_top_tier, \
                        winner_jungler_summoner_id, winner_jungler_champion_id, winner_jungler_tier, \
                        winner_mid_summoner_id, winner_mid_champion_id, winner_mid_tier, \
                        winner_adc_summoner_id, winner_adc_champion_id, winner_adc_tier, \
                        winner_support_summoner_id, winner_support_champion_id, winner_support_tier, \
                        loser_top_summoner_id, loser_top_champion_id, loser_top_tier, \
                        loser_jungler_summoner_id, loser_jungler_champion_id, loser_jungler_tier, \
                        loser_mid_summoner_id, loser_mid_champion_id, loser_mid_tier, \
                        loser_adc_summoner_id, loser_adc_champion_id, loser_adc_tier, \
                        loser_support_summoner_id, loser_support_champion_id, loser_support_tier \
                        = row
                except ValueError:
                    continue # skip malformed lines

                self.known_match_ids.add(int(match_id))

                if '?' in row:
                    continue # skip matches with unknown data

                for summoner_id in (
                        winner_top_summoner_id,
                        winner_jungler_summoner_id,
                        winner_mid_summoner_id,
                        winner_adc_summoner_id,
                        winner_support_summoner_id,
                        loser_top_summoner_id,
                        loser_jungler_summoner_id,
                        loser_mid_summoner_id,
                        loser_adc_summoner_id,
                        loser_support_summoner_id,
                        ):
                    self.known_summoner_ids.add(int(summoner_id))

                for (champion_id, tier), position in zip((
                        (winner_top_champion_id, winner_top_tier),
                        (winner_jungler_champion_id, winner_jungler_tier),
                        (winner_mid_champion_id, winner_mid_tier),
                        (winner_adc_champion_id, winner_adc_tier),
                        (winner_support_champion_id, winner_support_tier),
                        ), riot.POSITIONS):
                    self.wins.setdefault(tier, {}).setdefault(position, {}).setdefault(int(champion_id), 0)
                    self.wins[tier][position][int(champion_id)] += 1

                for (champion_id, tier), position in zip((
                        (loser_top_champion_id, loser_top_tier),
                        (loser_jungler_champion_id, loser_jungler_tier),
                        (loser_mid_champion_id, loser_mid_tier),
                        (loser_adc_champion_id, loser_adc_tier),
                        (loser_support_champion_id, loser_support_tier),
                        ), riot.POSITIONS):
                    self.losses.setdefault(tier, {}).setdefault(position, {}).setdefault(int(champion_id), 0)
                    self.losses[tier][position][int(champion_id)] += 1

        # establish thread for shared printing
        match_print_queue = queue.Queue()
        PrintThread(match_print_queue, open(MATCH_FILE, 'a')).start()

        # fire up worker threads to actually perform roundtrips to the LOL API
        match_summoner_queue = queue.LifoQueue()
        for i in range(10):
            MatchCollectorThread(self.api, match_summoner_queue, match_print_queue, self.known_summoner_ids, self.known_match_ids, self.wins, self.losses).start()

        # kickstart worker threads with known summoner ids
        for summoner_id in self.known_summoner_ids:
            match_summoner_queue.put(summoner_id)

    def html(self, template, **kw):
        return lookup.get_template(template).render_unicode(**kw).encode('utf-8', 'replace')

    @cherrypy.expose
    def index(self):
        """Return the homepage."""
        return self.html('index.html', match_count=len(self.known_match_ids), summoner_count=len(self.known_summoner_ids))

    @cherrypy.expose
    def summoner(self, who):
        """Return a webpage with details about the given summoner."""

        def one_rec_per_position(recs):
            results = []
            for p in riot.POSITIONS:
                for rec in recs:
                    if rec.position == p:
                        results.append(rec)
                        break
                else:
                    results.append(Placeholder(p))
            for result in results:
                if not result.placeholder:
                    return results
            return []

        summoner_id, summoner = self.api.summoner_by_name(who)
        tier, division = self.api.tier_division(summoner_id)
        sc = self.summoner_perfomance(summoner_id, tier)
        climb_recs = [c for c in sc if c.sessions >= 10 and c.winrate_expected > .5][:5]
        position_recs = one_rec_per_position([c for c in sc if c.sessions >= 10])
        practice_recs = one_rec_per_position([c for c in sc if c.sessions < 10 and c.winrate_expected > .5])

        return self.html('summoner.html', summoner=summoner, tier=tier, division=division,
            climb_recs=climb_recs, position_recs=position_recs, practice_recs=practice_recs,
            match_count=len(self.known_match_ids), summoner_count=len(self.known_summoner_ids))

    def summoner_perfomance(self, summoner_id, tier):
        """Return a summary of how a summoner performs on all champions."""

        # process each match
        wins = {}
        losses = {}
        for match in self.api.matchhistory(summoner_id, multithread=True):
            match_id = match['matchId']
            if match['season'] != riot.CURRENT_SEASON:
                break

            if len(match['participants']) != 1:
                raise ValueError('Expected exactly one participant')
            participant = match['participants'][0]

            champion_id = participant['championId']
            timeline = participant['timeline']
            lane = timeline['lane']
            role = timeline['role']
            victory = participant['stats']['winner']

            position = riot.position(lane, role, champion_id)
            if position is None:
                continue # skip matches where we can't determine position

            if victory:
                wins.setdefault(position, {}).setdefault(champion_id, 0)
                wins[position][champion_id] += 1
            else:
                losses.setdefault(position, {}).setdefault(champion_id, 0)
                losses[position][champion_id] += 1

        # assemble results sorted by expected winrate
        results = []
        for position in riot.POSITIONS:
            win_champions = self.wins.get(tier, {}).get(position, {}).keys()
            loss_champions = self.losses.get(tier, {}).get(position, {}).keys()
            cw = wins.get(position, {})
            cl = losses.get(position, {})
            champion_ids = set(win_champions).union(loss_champions).union(cw.keys()).union(cl.keys())
            for champion_id in champion_ids:
                w = cw.get(champion_id, 0)
                l = cl.get(champion_id, 0)
                t = self.winrate_global(tier, position, champion_id)
                results.append(SummonerChampion(self.api, position, champion_id, t, w, l))
        return sorted(results, key=operator.attrgetter('winrate_expected'), reverse=True)

    def winrate_global(self, tier, position, champion_id):
        """Return the global winrate the given tier-position-champion combination."""
        w = self.wins.get(tier, {}).get(position, {}).get(champion_id, 0)
        l = self.losses.get(tier, {}).get(position, {}).get(champion_id, 0)
        k = max(1000 - w - l, 0) # smooth over 1000 matches
        return float((k * 0.5) + w) / (k + w + l) # assume midpoint winrate of 50%


class SummonerChampion:
    placeholder = False

    def __init__(self, api, position, champion_id, twr, w, l):
        self.position = position
        self.champion_id = champion_id
        self.champion_image = api.champion_image(champion_id)
        self.champion_name = api.champion_name(champion_id)
        if (w + l) > 0:
            self.winrate_summoner = w / float(w + l)
        else:
            self.winrate_summoner = None
        self.winrate_tier = twr
        k = max(10 - w - l, 0) # smooth over 10 matches
        self.winrate_expected = ((k * twr) + w) / (k + w + l)
        self.wins = w
        self.losses = l
        self.sessions = w + l


class Placeholder(SummonerChampion):
    placeholder = True

    def __init__(self, position):
        self.position = position


class MatchCollectorThread(threading.Thread):

    def __init__(self, api, summoner_queue, print_queue, known_summoner_ids, known_match_ids, wins, losses):
        threading.Thread.__init__(self, daemon=True)
        self.api = api
        self.summoner_queue = summoner_queue
        self.print_queue = print_queue
        self.known_summoner_ids = known_summoner_ids
        self.known_match_ids = known_match_ids
        self.wins = wins
        self.losses = losses

    def run(self):
        while True:
            summoner_id = self.summoner_queue.get()
            self.work(summoner_id)
            self.summoner_queue.task_done()

    def work(self, summoner_id):

        for match in self.api.matchhistory(summoner_id):

            match_id = match['matchId']
            if match_id in self.known_match_ids:
                continue # skip already observed matches
            self.known_match_ids.add(match_id)

            match_version = match['matchVersion']
            if not match_version.startswith(riot.CURRENT_VERSION):
                break

            # the matchhistory endpoint does not include information in all
            # participants within the match, to receive those we issue a second
            # call to the match endpoint.
            try:
                match = self.api.match(match_id)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    continue # skip matches that do not exist
                raise

            # create a mapping of participant ids to summoner ids
            summoner_ids = {}
            for identity in match['participantIdentities']:
                participant_id = identity['participantId']
                summoner_id = identity['player']['summonerId']
                summoner_ids[participant_id] = summoner_id

            # create a mapping of summoner ids to tier and divisions
            tier_divisions = self.api.tiers_divisions(summoner_ids.values())

            # collect data for each participant
            winners = {}
            losers = {}
            for participant in match['participants']:
                participant_id = participant['participantId']
                summoner_id = summoner_ids[participant_id]
                champion_id = participant['championId']
                stats = participant['stats']
                timeline = participant['timeline']
                lane = timeline['lane']
                role = timeline['role']
                tier = tier_divisions.get(summoner_id, ['?', '?'])[0]
                position = riot.position(lane, role, champion_id)
                if stats['winner']:
                    winners[position] = (summoner_id, champion_id, tier)
                    if tier != '?' and position is not None:
                        self.wins.setdefault(tier, {}).setdefault(position, {}).setdefault(champion_id, 0)
                        self.wins[tier][position][champion_id] += 1
                else:
                    losers[position] = (summoner_id, champion_id, tier)
                    if tier != '?' and position is not None:
                        self.losses.setdefault(tier, {}).setdefault(position, {}).setdefault(champion_id, 0)
                        self.losses[tier][position][champion_id] += 1

                # remember any newly discovered summoners in this match
                if summoner_id not in self.known_summoner_ids:
                    self.known_summoner_ids.add(summoner_id)
                    self.summoner_queue.put(summoner_id)

            # cheesy CSV formatting
            output = [match_id, match_version, match['matchCreation']]
            for participants in (winners, losers):
                # align participants ordering with position ordering
                for position in riot.POSITIONS:
                    output.extend(participants.get(position, ['?', '?', '?']))
            self.print_queue.put(','.join([str(i) for i in output]))


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


if __name__ == '__main__':
    """Launch the application."""

    parser = argparse.ArgumentParser()
    parser.add_argument('--production', dest='production', default=False, action='store_true',
        help='Is this running in production?')
    parser.add_argument('--host', metavar='HOST', default='127.0.0.1',
        help='What hostname should we listen on?')
    parser.add_argument('--port', metavar='PORT', type=int, default=8080,
        help='What port should we listen on?')
    args = parser.parse_args()

    # global cherrypy configuration
    global_cfg = {
        'server.socket_host': args.host,
        'server.socket_port': args.port,
    }
    if args.production:
        global_cfg['environment'] = 'production'
    cherrypy.config.update(global_cfg)

    # application configuration and start
    cfg = {
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': STATIC_DIR,
        }
    }
    cherrypy.quickstart(Lolfu(), '/', cfg)
