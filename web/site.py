#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name, and receive a webpage that advises them what are the winrate
optimal champions to play in each position. The optimization is performed
as a simple approach to the multi-armed bandit problem.

http://leagueoflegends.com
https://en.wikipedia.org/wiki/Multi-armed_bandit
"""

import cherrypy
import os
import os.path


class LOLBandit(object):
    """CherryPy application that allows League of Legends summoners to lookup their
    summoner by name and receive a webpage in return that advises them what are the
    winrate optimal champions to play in each position.
    """

    def html(self, title, body):
        """Return html for the given parameters."""
        return """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="utf-8">
                <meta http-equiv="X-UA-Compatible" content="IE=edge">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <!--TODO: add favicon-->
                <title>%s</title>
                <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">
                <link rel="stylesheet" href="static/style.css">
            </head>
            <body>
                <div class="container">

                    <form class="form-inline" method="get" action="who">
                        <div class="form-group">
                            <label class="sr-only" for="summoner_input">Summoner</label>
                            <input type="text" class="form-control input-lg" id="summoner_input" placeholder="Summoner Name" name="summoner">
                        </div>
                        <button type="submit" class="btn btn-default btn-lg">Go</button>
                    </form>

                    <h1>%s</h1>
                    <dl class="dl-horizontal">
                    <dt>Top</dt>
                    <dd>baz:</dd>
                    <dt>Jungle</dt>
                    <dd>baz:</dd>
                    <dt>Mid</dt>
                    <dd>baz:</dd>
                    <dt>ADC</dt>
                    <dd>baz:</dd>
                    <dt>Support</dt>
                    <dd>baz:</dd>
                    </dl>

                </div>
            </body>
            </html>""" % (title, body)

    @cherrypy.expose
    def index(self):
        return self.html('lolfu', '')

    @cherrypy.expose
    def who(self, summoner='Lyte'):
        """Return a webpage with details about the given summoner."""
        body='???'
        return self.html(summoner, body)


if __name__ == '__main__':
    """Launch the application on localhost:8080 for debugging."""
    cfg = {
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.abspath(os.getcwd()) + '/static'
        }
    }
    cherrypy.quickstart(LOLBandit(), '/', cfg)
