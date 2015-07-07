#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name, and receive a webpage that advises them what are the winrate
optimal champions to play in each position. The optimization is performed
as a simple approach to the multi-armed bandit problem.

http://leagueoflegends.com
https://en.wikipedia.org/wiki/Multi-armed_bandit
"""

import argparse
import cherrypy
import riot
import os
import os.path
from mako.lookup import TemplateLookup


lookup = TemplateLookup(
    directories=os.path.dirname(os.path.abspath(__file__)) + os.sep + 'html',
    module_directory=os.path.dirname(os.path.abspath(__file__)) + os.sep + 'tmp')


class LOLBandit(object):
    """CherryPy application that allows League of Legends summoners to lookup their
    summoner by name and receive a webpage in return that advises them what are the
    winrate optimal champions to play in each position.
    """

    def __init__(self):
        self.api = riot.RiotAPI()

    def html(self, template, **kw):
        return lookup.get_template(template).render_unicode(**kw).encode('utf-8', 'replace')

    @cherrypy.expose
    def index(self):
        return self.html('index.html')

    def recify(self, scs):
        recs = []
        for position in riot.POSITIONS:
            for champion_id, wins, losses, wrs, wrt, wre in scs.get(position, [])[:1]:
                if wre < 0.5:
                    break # don't recommend anything with less than 50% winrate
                rec = {}
                rec['position'] = position
                rec['champion_name'] = self.api.champion_name(champion_id)
                rec['champion_image'] = self.api.champion_image(champion_id)
                rec['champion_key'] = self.api.champion_key(champion_id)
                rec['winrate_summoner'] = wrs
                rec['winrate_tier'] = wrt
                rec['winrate_expected'] = wre
                rec['wins'] = wins
                rec['losses'] = losses
                recs.append(rec)
        return recs

    @cherrypy.expose
    def summoner(self, who):
        """Return a webpage with details about the given summoner."""

        summoner_id, summoner = self.api.summoner_by_name(who)
        tier, division = self.api.tier_division(summoner_id)
        exploit, explore, bandit = self.api.summoner_champion_summary(summoner_id, tier)
        exploit_recs = self.recify(exploit)
        explore_recs = self.recify(explore)
        bandit_recs = self.recify(bandit)

        return self.html('summoner.html', summoner=summoner, tier=tier, division=division,
            exploit_recs=exploit_recs, explore_recs=explore_recs, bandit_recs=bandit_recs)


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
            'tools.staticdir.dir': os.path.dirname(os.path.abspath(__file__)) + os.sep + 'static',
        }
    }
    cherrypy.quickstart(LOLBandit(), '/', cfg)
