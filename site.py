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
from mako.template import Template
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

    @cherrypy.expose
    def summoner(self, who='Lyte'):
        """Return a webpage with details about the given summoner."""
        summoner_id, summoner = self.api.summoner_by_name(who)
        tier, division = self.api.tier_division(summoner_id)
        recs = []
        for position in riot.POSITIONS:
            # TODO make this real
            rec0 = {}
            rec0['champion_name'] = self.api.champion_name(9)
            rec0['champion_image'] = self.api.champion_image(9)
            rec0['winrate_expected'] = .5453515
            rec0['winrate_summoner'] = None
            rec0['winrate_tier'] = .5453515
            rec0['wins'] = 110
            rec0['losses'] = 94
            recs.append((rec0, rec0, rec0))
        return self.html('summoner.html', summoner=summoner, tier=tier, division=division, recs=recs)


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
