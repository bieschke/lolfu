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
        matches = self.matches(summoner_id, matchlist)
        teams = self.teams(summoner_id, matches)
        return self.html('summoner_content.html', teams=teams)

    def matches(self, summoner_id, matchlist):
        summoner_cache = {}
        champion_cache = {}
        matches = []
        for m in matchlist:
            match_id = m['matchId']
            if match_id is None:
                continue # skip bogus matches
            match = self.api.match(match_id)
            if match is None:
                continue # skip matches that don't exist
            matches.append(Match(self.api, match_id, summoner_id, match, summoner_cache, champion_cache))
        return matches

    def teams(self, summoner_id, matches, game_min=10):
        # compute counts of how many games this summoner has played with teammates
        match_counts = {}
        for match in matches:
            for teammate in match.teammates:
                match_counts[teammate] = match_counts.get(teammate, 0) + 1

        # determine set of recurring teammates, anyone with N or more matches
        recurring = set(s for (s, count) in match_counts.items() if s.summoner_id == summoner_id or count >= game_min)

        # return all iterations of recurring teammate combinations that include the summoner
        solo_team = set(s for (s, count) in match_counts.items() if s.summoner_id == summoner_id)
        teams = []
        if len(recurring) > 1:
            teams.append(Team(solo_team, recurring.difference(solo_team))) # special team to capture *only* solo games
        for i in (1, 2, 3, 4, 5):
            for teammates in itertools.combinations(recurring, i):
                if summoner_id in (s.summoner_id for s in teammates):
                    teams.append(Team(teammates, set()))

        self.populate_team_stats(matches, teams)

        return sorted([t for t in teams if t.match_count > game_min], key=operator.attrgetter('match_count'), reverse=True)

    def populate_team_stats(self, matches, teams):
        for match in matches:
            if match.victory is None:
                continue # skip inscrutable victory conditions
            for summoner in match.teammates:
                summoner.victory(match.victory)
            for team in teams:
                # only accumulate stats if this team played this match
                if team.summoners.issubset(match.teammates) and not team.anti_summoners.intersection(match.teammates):
                    team.victory(match.victory)
                    for summoner in team.summoners:
                        sid = summoner.summoner_id
                        position = match.positions[sid]
                        champion = match.champions[sid]
                        if summoner and position and champion: # skip when data is uncertain
                            team.summoner_champion_position(summoner, position, champion, match.victory)


class Match:

    def __init__(self, api, match_id, summoner_id, api_dict, summoner_cache, champion_cache):
        self.match_id = match_id

        # map participants to summoners
        summoner_ids = {}
        summoner_names = {}
        for pid in api_dict['participantIdentities']:
            sid = pid['player']['summonerId']
            summoner_ids[pid['participantId']] = sid
            summoner_names[sid] = pid['player']['summonerName']

        # map participants to teams, champions, and positions
        teams = {}
        champions = {}
        positions = {}
        # determine victory
        self.victory = None
        for p in api_dict['participants']:
            pid = p['participantId']
            # participants to teams
            teams[pid] = p['teamId']
            # who won?
            if summoner_id == summoner_ids[pid]:
                self.victory = p['stats']['winner']
            # participants to champions
            cid = p['championId']
            champions[pid] = champion_cache.setdefault(cid, Champion(api, cid))
            # participants to positions
            # FIXME: "timeline" field always returned?
            positions[pid] = riot.position(p['timeline']['lane'], p['timeline']['role'])

        # calculate which team is this summoner's team
        teammate_team_id = None
        for pid, sid in summoner_ids.items():
            if sid == summoner_id:
                teammate_team_id = teams[pid]

        # calculate teammates for this match, include oneself
        self.teammates = set(
            summoner_cache.setdefault(sid, Summoner(sid, summoner_names[sid]))
            for (pid, sid) in summoner_ids.items()
            if teammate_team_id is not None and teams[pid] == teammate_team_id)

        # remember champions and positions for teammates
        self.champions = {sid:champions[pid] for (pid, sid) in summoner_ids.items()}
        self.positions = {sid:positions[pid] for (pid, sid) in summoner_ids.items()}

    def __eq__(self, other):
        return self.match_id == other.match_id

    def __hash__(self):
        return self.match_id


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


class Winrate:

    def __init__(self):
        self.wins = 0
        self.losses = 0

    @property
    def match_count(self):
        return self.wins + self.losses

    @property
    def winrate(self):
        return self.wins / float(self.wins + self.losses)

    @property
    def k(self):
        return max(10 - self.wins - self.losses, 0) # smooth over 10 matches

    @property
    def winrate_expected(self):
        return ((self.k * 0.5) + self.wins) / (self.k + self.match_count)

    @property
    def winrate_pessimistic(self):
        return ((self.k * 0.0) + self.wins) / (self.k + self.match_count)

    def victory(self, victory):
        if victory:
            self.wins += 1
        else:
            self.losses += 1


class Summoner(Winrate):

    def __init__(self, summoner_id, name):
        super(Summoner, self).__init__()
        self.summoner_id = summoner_id
        self.name = name

    def __eq__(self, other):
        return self.summoner_id == other.summoner_id

    def __hash__(self):
        return self.summoner_id


class Team(Winrate):

    def __init__(self, summoners, anti_summoners):
        super(Team, self).__init__()
        self.summoners = set(summoners)
        self.anti_summoners = set(anti_summoners)
        self.spc = {}

    @property
    def climb_recs(self):
        return sorted(
            [spc for spc in self.spc.values() if spc.winrate > 0.5],
            key=operator.attrgetter('winrate_pessimistic', 'match_count'), reverse=True)[:5]

    @property
    def label(self):
        l = ', '.join([s.name for s in sorted(self.summoners, key=operator.attrgetter('match_count'), reverse=True)])
        if len(self.summoners) == 1 and self.anti_summoners:
            l += ' (Solo)'
        return l

    @property
    def position_recs(self):
        position_recs = []
        for p in riot.POSITIONS:
            for rec in sorted(self.spc.values(), key=operator.attrgetter('winrate_expected', 'match_count'), reverse=True):
                if rec.position == p:
                    position_recs.append(rec)
                    break
        return position_recs

    @property
    def summoner_position_champions(self):
        return sorted(self.spc.values(), key=operator.attrgetter('match_count', 'winrate_expected'), reverse=True)

    def summoner_champion_position(self, summoner, position, champion, victory):
        key = (summoner, position, champion)
        self.spc.setdefault(key, SummonerPositionChampion(summoner, position, champion)).victory(victory)


class SummonerPositionChampion(Winrate):

    def __init__(self, summoner, position, champion):
        super(SummonerPositionChampion, self).__init__()
        self.summoner = summoner
        self.position = position
        self.champion = champion


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
