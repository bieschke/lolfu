#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name and receive a webpage that advises them about which champions to play.

http://leagueoflegends.com
"""

import argparse
import cherrypy
import json
import operator
import os
import os.path
import riot
import sys
import threading
import time
import queue
from mako.lookup import TemplateLookup


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'
HTML_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'html'
STATIC_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'static'
TMP_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'tmp'


lookup = TemplateLookup(directories=HTML_DIR, module_directory=TMP_DIR)


class MatchIdThread(threading.Thread):

    def __init__(self, match_queue, start_id):
        threading.Thread.__init__(self, daemon=True)
        self.match_queue = match_queue
        self.next_id = start_id

    def run(self):
        while True:
            self.match_queue.put(self.next_id)
            self.next_id += 1


class MatchCollectorThread(threading.Thread):

    def __init__(self, api, match_queue):
        threading.Thread.__init__(self, daemon=True)
        self.api = api
        self.match_queue = match_queue

    def run(self):
        while True:
            match_id = self.match_queue.get()
            match = self.api.match(match_id)
            if match and match['queueType'] == riot.SOLOQUEUE:
                for identity in match['participantIdentities']:
                    self.api.tier(int(identity['player']['summonerId']))
            self.match_queue.task_done()


class FuncWaitRepeatThread(threading.Thread):

    def __init__(self, func, wait):
        threading.Thread.__init__(self, daemon=True)
        self.func = func
        self.wait = wait

    def run(self):
        while True:
            self.func()
            time.sleep(self.wait)


class Lolfu:
    """CherryPy application that allows League of Legends summoners to lookup their
    summoner by name and receive a webpage in return that advises them what are the
    winrate optimal champions to play in each position.
    """
    MATCH_START_ID = 1886626000 # FIXME

    def __init__(self, background_threads):
        self.api = riot.RiotAPI(DATA_DIR)
        self.match_count = 0
        self.wins = {}
        self.losses = {}

        # spawn threads to collect match data in the background
        match_queue = queue.Queue(background_threads * 2)
        MatchIdThread(match_queue, self.MATCH_START_ID).start()
        for i in range(background_threads):
            MatchCollectorThread(self.api, match_queue).start()

        # update stats waiting one hour between
        FuncWaitRepeatThread(self.update_stats, 60 * 60).start()

    def update_stats(self):
        match_count = 0
        wins = {}
        losses = {}

        for root, dirs, files in os.walk(DATA_DIR + os.sep + 'match'):
            for name in files:
                with open(os.path.join(root, name), 'r') as f:
                    match = json.load(f)
                    if match['season'] != riot.CURRENT_SEASON:
                        break
                    if match['queueType'] != riot.SOLOQUEUE:
                        break
                    #if not match['matchVersion'].startswith(riot.CURRENT_VERSION):
                    #    break

                # create a mapping of participant ids to summoner ids
                summoner_ids = {}
                for identity in match['participantIdentities']:
                    participant_id = identity['participantId']
                    summoner_id = int(identity['player']['summonerId'])
                    summoner_ids[participant_id] = summoner_id

                # collect data for each participant
                for participant in match['participants']:
                    participant_id = participant['participantId']
                    summoner_id = int(summoner_ids[participant_id])
                    champion_id = int(participant['championId'])
                    timeline = participant['timeline']
                    lane = timeline['lane']
                    role = timeline['role']
                    position = riot.position(lane, role, champion_id)
                    tier = self.api.tier(summoner_id)
                    if position and tier:
                        if participant['stats']['winner']:
                            wins.setdefault(tier, {}).setdefault(position, {}).setdefault(champion_id, 0)
                            wins[tier][position][champion_id] += 1
                        else:
                            losses.setdefault(tier, {}).setdefault(position, {}).setdefault(champion_id, 0)
                            losses[tier][position][champion_id] += 1
                        match_count += 1

        self.match_count, self.wins, self.losses = match_count, wins, losses
        cherrypy.log('%d matches loaded' % self.match_count)

    def html(self, template, **kw):
        return lookup.get_template(template).render_unicode(**kw).encode('utf-8', 'replace')

    @cherrypy.expose
    def index(self):
        """Return the homepage."""
        return self.html('index.html', match_count=self.match_count, version=riot.CURRENT_VERSION)

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

        summoner = self.api.summoner_by_name(who)
        sc = self.summoner_perfomance(summoner.summoner_id, summoner.tier)
        climb_recs = [c for c in sc if c.sessions >= 10 and c.winrate_expected > .5][:5]
        position_recs = one_rec_per_position([c for c in sc if c.sessions >= 10])
        practice_recs = one_rec_per_position([c for c in sc if c.sessions < 10 and c.winrate_expected > .5])

        return self.html('summoner.html', summoner=summoner,
            match_count=self.match_count, version=riot.CURRENT_VERSION,
            climb_recs=climb_recs, position_recs=position_recs, practice_recs=practice_recs)

    def summoner_perfomance(self, summoner_id, tier):
        """Return a summary of how a summoner performs on all champions."""

        # process each match
        wins = {}
        losses = {}
        for match in self.api.matchlist(summoner_id):
            champion_id = match['champion']

            position = riot.position(match['lane'], match['role'], champion_id)
            if position is None:
                continue # skip matches where we can't determine position

            victory = self.api.victory(match['matchId'], summoner_id)
            if victory is None:
                continue # skip inscrutable victory conditions

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



if __name__ == '__main__':
    """Launch the application."""

    parser = argparse.ArgumentParser()
    parser.add_argument('--production', dest='production', default=False, action='store_true',
        help='Is this running in production?')
    parser.add_argument('--host', metavar='HOST', default='127.0.0.1',
        help='What hostname should we listen on?')
    parser.add_argument('--port', metavar='PORT', type=int, default=8080,
        help='What port should we listen on?')
    parser.add_argument('--access-log', default=None,
        help='What file should we write access logs to?')
    parser.add_argument('--error-log', default=None,
        help='What file should we write error logs to?')
    parser.add_argument('--background-threads', type=int, default=1,
        help='How many background threads should we use to collect data?')
    args = parser.parse_args()

    # global cherrypy configuration
    global_cfg = {
        'server.socket_host': args.host,
        'server.socket_port': args.port,
        'log.access_file': args.access_log,
        'log.error_file': args.error_log,
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
    cherrypy.quickstart(Lolfu(args.background_threads), '/', cfg)
