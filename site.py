#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name and receive a webpage that advises them about which champions to play.

http://leagueoflegends.com
"""

import argparse
import cherrypy
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
SUMMONER_FILE = DATA_DIR + os.sep + 'summoner.csv'
WINRATE_FILE = DATA_DIR + os.sep + 'winrate.csv'


lookup = TemplateLookup(directories=HTML_DIR, module_directory=TMP_DIR)


class Lolfu:
    """CherryPy application that allows League of Legends summoners to lookup their
    summoner by name and receive a webpage in return that advises them what are the
    winrate optimal champions to play in each position.
    """

    def __init__(self):
        self.api = riot.RiotAPI()
        self.background_match_collection()

    def background_match_collection(self):
        """Launch daemon threads to collect match data."""

        # accumulate all of the match ids for which we have already collected data
        known_match_ids = set()
        known_summoner_ids = set()
        with open(MATCH_FILE, 'r') as f:
            for line in f:
                # rely on the first column being the match id
                known_match_ids.add(int(line.split(',')[0]))
                # these column indexes are summoner ids
                for i in (3, 6, 9, 12, 15, 18, 21, 24, 27, 30):
                    val = line.split(',')[i]
                    try:
                        known_summoner_ids.add(int(val))
                    except ValueError:
                        pass # unknown summoner ids won't parse here
        print('%d preexisting matches found' % len(known_match_ids), file=sys.stderr)
        print('%d preexisting summoners found' % len(known_summoner_ids), file=sys.stderr)

        # establish thread for shared printing
        match_print_queue = queue.Queue()
        PrintThread(match_print_queue, open(MATCH_FILE, 'a')).start()

        # fire up worker threads to actually perform roundtrips to the LOL API
        match_summoner_queue = queue.Queue()
        for i in range(100):
            MatchCollectorThread(self.api, match_summoner_queue, match_print_queue, known_summoner_ids, known_match_ids).start()

        # kickstart worker threads with known summoner ids
        for summoner_id in known_summoner_ids:
            match_summoner_queue.put(summoner_id)

    def html(self, template, **kw):
        return lookup.get_template(template).render_unicode(**kw).encode('utf-8', 'replace')

    @cherrypy.expose
    def index(self):
        return self.html('index.html')

    @cherrypy.expose
    def summoner(self, who):
        """Return a webpage with details about the given summoner."""

        def one_rec_per_position(recs):
            class Placeholder:
                placeholder = True
                def __init__(self, p):
                    self.position = p
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
        sc = self.api.summoner_champion_summary(summoner_id, tier)
        climb_recs = [c for c in sc if c.sessions >= 10 and c.winrate_expected > .5][:5]
        position_recs = one_rec_per_position([c for c in sc if c.sessions >= 10])
        practice_recs = one_rec_per_position([c for c in sc if c.sessions < 10 and c.winrate_expected > .5])

        return self.html('summoner.html', summoner=summoner, tier=tier, division=division,
            climb_recs=climb_recs, position_recs=position_recs, practice_recs=practice_recs)


class MatchCollectorThread(threading.Thread):

    def __init__(self, api, summoner_queue, print_queue, known_summoner_ids, known_match_ids):
        threading.Thread.__init__(self, daemon=True)
        self.api = api
        self.summoner_queue = summoner_queue
        self.print_queue = print_queue
        self.known_summoner_ids = known_summoner_ids
        self.known_match_ids = known_match_ids

    def run(self):
        while True:
            summoner_id = self.summoner_queue.get()
            self.work(summoner_id)
            self.summoner_queue.task_done()

    def work(self, summoner_id):
        abort = False
        begin_index = 0
        step = 15 # maximum allowable through Riot API
        while not abort:
            abort = False

            # walk through summoner's match history STEP matches at a time
            end_index = begin_index + step
            matches = self.api.matchhistory(summoner_id, begin_index, end_index).get('matches', [])
            if not matches:
                break
            begin_index += step

            for match in matches:

                match_id = match['matchId']
                if match_id in self.known_match_ids:
                    continue # skip already observed matches
                self.known_match_ids.add(match_id)

                match_version = match['matchVersion']
                if not match_version.startswith(riot.CURRENT_VERSION):
                    abort = True
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
                    else:
                        losers[position] = (summoner_id, champion_id, tier)

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
