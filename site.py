#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name, and receive a webpage that advises them what are the winrate
optimal champions to play in each position. The optimization is performed
as a simple approach to the multi-armed bandit problem.

http://leagueoflegends.com
https://en.wikipedia.org/wiki/Multi-armed_bandit
"""

import cherrypy
import riot
import os.path
from mako.template import Template
from mako.lookup import TemplateLookup


lookup = TemplateLookup(directories='html', module_directory='tmp')


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
    def who(self, summoner='Lyte'):
        """Return a webpage with details about the given summoner."""
        summoner_id, summoner = self.api.summoner_by_name(summoner)
        tier, division = self.api.tier_division(summoner_id)
        return self.html('who.html', summoner=summoner, tier=tier, division=division)


if __name__ == '__main__':
    """Launch the application on localhost:8080 for debugging."""
    cfg = {
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.dirname(os.path.abspath(__file__)) + '/static'
        }
    }
    cherrypy.quickstart(LOLBandit(), '/', cfg)
