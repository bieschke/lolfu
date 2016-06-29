#!/usr/bin/env python3.4
"""League of Legends website that allows players to look up their summoner
by name and receive a webpage that advises them about which champions to play.

http://leagueoflegends.com
"""

import asyncio
import argparse
import cherrypy
import csv
import itertools
import operator
import os
import os.path
import queue
import random
import riot
import threading
import urllib.parse
from mako.lookup import TemplateLookup


DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'data'
HTML_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'html'
STATIC_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'static'
FONT_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'static' + os.sep + 'fonts'
FRONTPAGE_DIR = os.path.join(STATIC_DIR, 'img', 'splash', 'frontpage')
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
        self.splashes = os.listdir(FRONTPAGE_DIR)

        # summoner page init
        self.summoner_queue = queue.Queue()
        DataCollectorThread(self.api, self.summoner_queue).start()

        # stats page init
        # load kill stats from csv file
        self.kill_stats = {}
        with open(os.path.join(DATA_DIR, 'kill_stats.csv'), newline='') as f:
            for w, l, uk, tk in csv.reader(f):
                self.kill_stats[tuple(int(x) for x in (uk, tk))] = tuple(int(x) for x in (w, l))
        # load tower stats from csv file
        self.tower_stats = {}
        with open(os.path.join(DATA_DIR, 'tower_stats.csv'), newline='') as f:
            for w, l, ui, ut, ti, tt in csv.reader(f):
                self.tower_stats[tuple(int(x) for x in (ui, ut, ti, tt))] = tuple(int(x) for x in (w, l))
        # load joint stats from csv file
        self.joint_stats = {}
        with open(os.path.join(DATA_DIR, 'joint_stats.csv'), newline='') as f:
            for w, l, ui, ut, uk, ti, tt, tk in csv.reader(f):
                self.joint_stats[tuple(int(x) for x in (ui, ut, uk, ti, tt, tk))] = tuple(int(x) for x in (w, l))

        # pool page init
        self.weights = {}
        self.matchups = {}
        with open(os.path.join(DATA_DIR, 'matchup_stats.csv'), newline='') as f:
            for row in csv.reader(f):
                champion1, champion2, w, l = (int(x) for x in row)
                self.matchups.setdefault(champion1, {})
                self.matchups[champion1][champion2] = (w, l)
                self.weights.setdefault(champion1, 0)
                self.weights[champion1] += w + l
                self.weights.setdefault(champion2, 0)
                self.weights[champion2] += w + l
        weight_total = sum(self.weights.values())
        for key in self.weights:
            self.weights[key] *= 10.0 # account for 10 summoners/game
            self.weights[key] /= weight_total

    def html(self, template, **kw):
        return lookup.get_template(template).render_unicode(**kw).encode('utf-8', 'replace')

    def random_splash(self):
        return random.choice(self.splashes)

    @cherrypy.expose
    def index(self, who=None):
        """Return either the app homepage or the summoner's homepage."""

        if who:
            summoner = self.api.summoner_by_name(who)
            if summoner:
                # queue this summoner's data to be collected in a background thread
                self.summoner_queue.put(summoner.summoner_id)
                return self.html('summoner.html', summoner=summoner)
            else:
                return self.html('index.html', random_splash=self.random_splash(), error=who)

        return self.html('index.html', random_splash=self.random_splash())

    @cherrypy.expose
    def pool(self):
        champions = [(cid, self.api.champion_image(cid)) for cid in self.api.champion_ids()]
        return self.html('pool.html', champions=sorted(champions, key=operator.itemgetter(1)))

    @cherrypy.expose
    def pool_content(self, **champions):

        class Pool:
            def __init__(self, denominator):
                self.numerator = 0
                self.denominator = denominator
                self.favored = 0
                self.unfavored = 0
            @property
            def weighted_winrate(self):
                return 100.0 * self.numerator / self.denominator

        class Champion(Pool):
            def __init__(self, api, champion_id, denominator):
                super(Champion, self).__init__(denominator)
                self.champion_id = champion_id
                self.champion_image = api.champion_image(champion_id)
                self.champion_name = api.champion_name(champion_id)
                self.champion_key = api.champion_key(champion_id)
                self.counterpicks = 0

        class Matchup:
            def __init__(self, api, weights, champion_id, opponent_id, w, l):
                self.weights = weights
                self.champion_id = champion_id
                self.champion_image = api.champion_image(champion_id)
                self.champion_name = api.champion_name(champion_id)
                self.champion_key = api.champion_key(champion_id)
                self.opponent_id = opponent_id
                self.opponent_image = api.champion_image(opponent_id)
                self.opponent_name = api.champion_name(opponent_id)
                self.opponent_key = api.champion_key(opponent_id)
                self.wins = w
                self.losses = l
                self.winrate = 100.0 * self.wins / (self.wins + self.losses)
            @property
            def weight(self):
                return self.weights.get(self.opponent_id, 0.0)

        def pool_compute(champion_ids):
            denominator = sum(self.weights.values())

            pool_champions = [Champion(self.api, int(c), denominator) for c in champion_ids]

            matchups = []
            for champion in pool_champions:
                for opponent_id in self.matchups.get(champion.champion_id, {}):
                    wins, losses = self.matchups[champion.champion_id][opponent_id]
                    matchup = Matchup(self.api, self.weights, champion.champion_id, opponent_id, wins, losses)
                    champion.numerator += self.weights.get(opponent_id, 0.0) * wins / (wins + losses)
                    if matchup.winrate > 50.0:
                        champion.favored += 1
                    elif matchup.winrate < 50.0:
                        champion.unfavored += 1
                    matchups.append(matchup)

            pool_stats = Pool(denominator)
            pool_matchups = []
            for matchup in sorted(matchups, key=operator.attrgetter('winrate'), reverse=True):
                if matchup.opponent_id not in [m.opponent_id for m in pool_matchups]:
                    pool_stats.numerator += matchup.weight * matchup.wins / (matchup.wins + matchup.losses)
                    if matchup.winrate > 50.0:
                        pool_stats.favored += 1
                    elif matchup.winrate < 50.0:
                        pool_stats.unfavored += 1
                    pool_matchups.append(matchup)
                    for champion in pool_champions:
                        if champion.champion_id == matchup.champion_id:
                            champion.counterpicks += 1

            return sorted(pool_champions, key=operator.attrgetter('weighted_winrate'), reverse=True), \
                pool_stats, \
                sorted(pool_matchups, key=operator.attrgetter('weight'), reverse=True)

        # compute value of current champion pool
        champion_ids = set(champions.values())
        pool_champions, pool_stats, pool_matchups = pool_compute(champion_ids)

        return self.html('pool_content.html', pool_stats=pool_stats, pool_champions=pool_champions, matchups=pool_matchups);

    @cherrypy.expose
    def stats(self):
        return self.html('stats.html')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stats_joint(self, youri, yourt, yourk, theiri, theirt, theirk):
        stats = self.joint_stats.get(tuple(int(x) for x in (youri, yourt, yourk, theiri, theirt, theirk)), (0, 0))
        return {'wins' : stats[0], 'losses' : stats[1]}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stats_tower(self, youri, yourt, theiri, theirt):
        stats = self.tower_stats.get(tuple(int(x) for x in (youri, yourt, theiri, theirt)), (0, 0))
        return {'wins' : stats[0], 'losses' : stats[1]}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stats_kill(self, yourk, theirk):
        stats = self.kill_stats.get(tuple(int(x) for x in (yourk, theirk)), (0, 0))
        return {'wins' : stats[0], 'losses' : stats[1]}

    @cherrypy.expose
    def summoner(self, who):
        """Return a webpage with details about the given summoner."""
        summoner = self.api.summoner_by_name(who)
        if not summoner:
            raise cherrypy.HTTPRedirect('/?who=' + urllib.parse.quote(who), 307)
        raise cherrypy.HTTPRedirect('/' + summoner.standardized_name, 301)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def summoner_check(self, summoner_id):
        known, total = self.api.matchlist_check(summoner_id)
        return {'known':known, 'total':total}

    @cherrypy.expose
    def summoner_content(self, summoner_id):
        summoner_id = int(summoner_id)
        matchlist = self.api.matchlist(summoner_id)
        teammates = self.teammates(summoner_id, matchlist)
        teams = self.teams(summoner_id, matchlist, teammates)
        return self.html('summoner_content.html', teams=teams)

    def teammates(self, summoner_id, matchlist, game_min=10):
        # compute counts of how many games this summoner has played with teammates
        teammate_counts = {}
        for m, match, position, champion_id, teammates in self.walk_matches(summoner_id, matchlist):
            # increment the count for how may games this summoner has played with these teammates
            for teammate in teammates:
                teammate_counts[teammate] = teammate_counts.get(teammate, 0) + 1

        # determine set of recurring teammates, anyone with N or more matches
        return set(s for (s, count) in teammate_counts.items() if count >= game_min)

    def teams(self, summoner_id, matchlist, teammates):
        teams = []
        for i in (1, 2, 3, 4, 5):
            for team_summoners in itertools.combinations(teammates, i):
                if summoner_id in (s.summoner_id for s in team_summoners):
                    teams.append(Team(team_summoners, self.match_results(summoner_id, matchlist, set(team_summoners))))
        return teams

    def walk_matches(self, summoner_id, matchlist):
        for m in matchlist:
            match_id = m['matchId']
            match = self.api.match(match_id)

            if match is None:
                continue # ignore matches that don't exist

            position = riot.position(m['lane'], m['role'])
            if position is None:
                continue # ignore matches with no clear position

            champion_id = m['champion']
            if champion_id is None:
                continue # ignore matches with unidentified champions

            # map participants to summoners
            summoner_ids = {}
            summoner_names = {}
            for pid in match['participantIdentities']:
                sid = pid['player']['summonerId']
                summoner_ids[pid['participantId']] = sid
                summoner_names[sid] = pid['player']['summonerName']

            # map participants to teams
            teams = {}
            for p in match['participants']:
                teams[p['participantId']] = p['teamId']

            # calculate which team is on this summoner's team
            teammate_team_id = None
            for participant_id, sid in summoner_ids.items():
                if sid == summoner_id:
                    teammate_team_id = teams[participant_id]
                    break
            else:
                continue # ignore matches where we cannot determine team

            # calculate teammates for this match, include oneself
            teammates = set(Summoner(sid, summoner_names[sid]) for (pid, sid) in summoner_ids.items() if teams[pid] == teammate_team_id)

            yield m, match, position, champion_id, teammates

    def match_results(self, summoner_id, matchlist, required_teammates):

        # compute win and loss counts for position-champion combinations
        wins = {}
        losses = {}
        for m, match, position, champion_id, teammates in self.walk_matches(summoner_id, matchlist):
            if required_teammates.issubset(teammates):

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

                # tally wins and losses
                if victory is None:
                    continue # skip inscrutable victory conditions
                elif victory:
                    wins.setdefault(position, {}).setdefault(champion_id, 0)
                    wins[position][champion_id] += 1
                else:
                    losses.setdefault(position, {}).setdefault(champion_id, 0)
                    losses[position][champion_id] += 1

        # assemble results
        results = []
        for position in riot.POSITIONS:
            cw = wins.get(position, {})
            cl = losses.get(position, {})
            for champion_id in set(cw.keys()).union(cl.keys()):
                w = cw.get(champion_id, 0)
                l = cl.get(champion_id, 0)
                results.append(SummonerChampion(self.api, position, champion_id, w, l))

        return sorted(results, key=operator.attrgetter('sessions', 'winrate_expected'), reverse=True)


class Summoner:

    def __init__(self, summoner_id, name):
        self.summoner_id = summoner_id
        self.name = name

    def __eq__(self, other):
        return self.summoner_id == other.summoner_id

    def __hash__(self):
        return self.summoner_id


class Champion:

    def __init__(self, api, champion_id):
        self.champion_id = champion_id
        self.image = api.champion_image(champion_id)
        self.name = api.champion_name(champion_id)
        self.key = api.champion_key(champion_id)

    def __eq__(self, other):
        return self.champion_id == other.champion_id

    def __hash__(self):
        return self.champion_id


class SummonerChampion:

    def __init__(self, api, position, champion_id, w, l):
        self.position = position
        self.champion = Champion(api, champion_id)
        self.winrate_summoner = w / float(w + l)
        k = max(10 - w - l, 0) # smooth over 10 matches
        self.winrate_expected = ((k * 0.5) + w) / (k + w + l)
        self.winrate_pessimistic = ((k * 0.0) + w) / (k + w + l)
        self.wins = w
        self.losses = l
        self.sessions = w + l


class Team:

    def __init__(self, summoners, summoner_champions):
        self.heading = ', '.join([s.name for s in summoners])
        self.subheading = 'TODO matches'
        self.summoner_champions = summoner_champions
        self.climb_recs = sorted(
            [c for c in summoner_champions if c.winrate_summoner > 0.5],
            key=operator.attrgetter('winrate_pessimistic', 'sessions'), reverse=True)[:5]
        self.position_recs = []
        for p in riot.POSITIONS:
            for rec in sorted(summoner_champions, key=operator.attrgetter('winrate_expected', 'sessions'), reverse=True):
                if rec.position == p:
                    self.position_recs.append(rec)
                    break


class DataCollectorThread(threading.Thread):

    def __init__(self, api, summoner_queue):
        super(DataCollectorThread, self).__init__(name='DataCollector', daemon=True)
        self.api = api
        self.summoner_queue = summoner_queue

    @asyncio.coroutine
    def add_summoner(self, session, summoner_id):
        matchlist = self.api.matchlist(summoner_id)
        yield from asyncio.wait([self.api.match_async(session, m['matchId']) for m in matchlist if m])

    def process_summoner(self, summoner_id):
        session = riot.ClientSession()
        try:
            asyncio.get_event_loop().run_until_complete(self.add_summoner(session, summoner_id))
        finally:
            session.close()

    def run(self):
        while True:
            summoner_id = self.summoner_queue.get()
            try:
                self.process_summoner(summoner_id)
            except Exception as e:
                print('...summoner_id', summoner_id, 'error', repr(str(e)))
            self.summoner_queue.task_done()


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
    cherrypy.tree.mount(None, '/favicon.ico', { '/' : { 'tools.staticfile.on': True, 'tools.staticfile.filename': os.path.join(STATIC_DIR, 'favicon.ico') }})
    cherrypy.quickstart(Lolfu(), '/')
