#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name and receive a webpage that advises them about which champions to play.

http://leagueoflegends.com
"""

import asyncio
import argparse
import cherrypy
import operator
import os
import os.path
import riot
from mako.lookup import TemplateLookup


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'
HTML_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'html'
STATIC_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'static'
FONT_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'static' + os.sep + 'fonts'
TMP_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'tmp'


lookup = TemplateLookup(directories=HTML_DIR, module_directory=TMP_DIR)


@cherrypy.popargs('who')
class Lolfu:
    """CherryPy application that allows League of Legends summoners to lookup their
    summoner by name and receive a webpage in return that advises them what are the
    winrate optimal champions to play in each position.
    """

    def __init__(self):
        self.api = riot.RiotAPI(cherrypy, DATA_DIR)

    def html(self, template, **kw):
        return lookup.get_template(template).render_unicode(**kw).encode('utf-8', 'replace')

    @cherrypy.expose
    def index(self, who=None):
        """Return either the app homepage or the summoner's homepage."""

        if who:

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
            sc = self.summoner_perfomance(summoner.summoner_id)
            climb_recs = [c for c in sc if c.sessions >= 10 and c.winrate_expected > .5][:5]
            position_recs = one_rec_per_position(sc)
            sc = sorted(sc, key=operator.attrgetter('sessions', 'winrate_expected'), reverse=True)

            return self.html('summoner.html', summoner=summoner, climb_recs=climb_recs, position_recs=position_recs, sc=sc)

        return self.html('index.html')

    @cherrypy.expose
    def summoner(self, who):
        """Return a webpage with details about the given summoner."""
        summoner = self.api.summoner_by_name(who)
        raise cherrypy.HTTPRedirect('/' + summoner.standardized_name, 301)

    def summoner_perfomance(self, summoner_id):
        """Return a summary of how a summoner performs on all champions."""

        @asyncio.coroutine
        def run():
            positions = dict([(m['matchId'], riot.position(m['lane'], m['role'], m['champion'])) for m in matchlist])
            champions = dict([(m['matchId'], m['champion']) for m in matchlist])

            chunk = 10
            ml = list(matchlist)
            while ml:

                tasks = [self.api.match_async(session, m['matchId']) for m in ml[:chunk] if positions[m['matchId']]] # skip matches with no position
                del ml[:chunk]
                for f in asyncio.as_completed(tasks):
                    try:
                        match = yield from f
                    except Exception as e:
                        cherrypy.log(repr(e))
                        continue

                    match_id = match['matchId']
                    position = positions[match_id]
                    champion_id = champions[match_id]

                    # map participants to summoners
                    summoner_ids = {}
                    for pid in match['participantIdentities']:
                        summoner_ids[pid['participantId']] = pid['player']['summonerId']

                    # determine victory
                    victory = None
                    for participant in match['participants']:
                        if summoner_id == summoner_ids[participant['participantId']]:
                            victory = participant['stats']['winner']
                            break

                    if victory is None:
                        continue # skip inscrutable victory conditions
                    elif victory:
                        wins.setdefault(position, {}).setdefault(champion_id, 0)
                        wins[position][champion_id] += 1
                    else:
                        losses.setdefault(position, {}).setdefault(champion_id, 0)
                        losses[position][champion_id] += 1

        wins = {}
        losses = {}
        matchlist = self.api.matchlist(summoner_id)

        # parallelize network calls for each match
        session = riot.ClientSession()
        try:
            asyncio.get_event_loop().run_until_complete(run())
        finally:
            session.close()

        # assemble results sorted by expected winrate
        results = []
        for position in riot.POSITIONS:
            cw = wins.get(position, {})
            cl = losses.get(position, {})
            for champion_id in set(cw.keys()).union(cl.keys()):
                w = cw.get(champion_id, 0)
                l = cl.get(champion_id, 0)
                results.append(SummonerChampion(self.api, position, champion_id, w, l))
        return sorted(results, key=operator.attrgetter('winrate_expected', 'sessions'), reverse=True)


class SummonerChampion:
    placeholder = False

    def __init__(self, api, position, champion_id, w, l):
        self.position = position
        self.champion_id = champion_id
        self.champion_image = api.champion_image(champion_id)
        self.champion_name = api.champion_name(champion_id)
        self.champion_key = api.champion_key(champion_id)
        if (w + l) > 0:
            self.winrate_summoner = w / float(w + l)
        else:
            self.winrate_summoner = None
        k = max(10 - w - l, 0) # smooth over 10 matches
        self.winrate_expected = ((k * 0.5) + w) / (k + w + l)
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
    cherrypy.tree.mount(None, '/static', { '/' : { 'tools.staticdir.on': True, 'tools.staticdir.dir': STATIC_DIR }})
    cherrypy.tree.mount(None, '/fonts', { '/' : { 'tools.staticdir.on': True, 'tools.staticdir.dir': FONT_DIR }})
    cherrypy.quickstart(Lolfu(), '/')
