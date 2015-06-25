#!/usr/bin/env python
"""Work-in-progress
"""

import riot

api = riot.RiotAPI()

total_predictions = 0
correct_predictions = 0
known_summoner_ids = api.bootstrap_summoner_ids.copy()
remaining_summoner_ids = known_summoner_ids.copy()
while remaining_summoner_ids:
    summoner_id = remaining_summoner_ids.pop()
    print
    print
    print
    summoner_name = api.summoner_name(summoner_id)
    print 'Summoner %s' % summoner_name

    for game in api.recent_games(summoner_id).get('games', []):
        print
        game_mode = game.get('gameMode')
        game_type = game.get('gameType')
        game_subtype = game.get('subType')
        if game_mode != 'CLASSIC' or game_type != 'MATCHED_GAME' or game_subtype != 'RANKED_SOLO_5x5':
            print 'Skipping Game: %s %s %s' % (game_mode, game_type, game_subtype)
            continue

        team_id = game['teamId']
        champion_id = game['championId']
        champion_name = api.champion_name(champion_id)
        win_rate = api.summoner_champion_winrate(summoner_id, champion_id)
        predict = win_rate
        win = game['stats']['win']
        print 'Summoner %s played champion %s on team %s having winrate %.0f%% for a %s' % (summoner_name, champion_name, team_id, 100 * win_rate, win and 'WIN' or 'LOSS')

        for fellow in game['fellowPlayers']:
            same_team = team_id == fellow['teamId']
            fellow_id = fellow['summonerId']
            if fellow_id not in known_summoner_ids:
                known_summoner_ids.add(fellow_id)
                remaining_summoner_ids.add(fellow_id)
            fellow_name = api.summoner_name(fellow_id)
            fellow_champion_name = api.champion_name(fellow['championId'])
            fellow_win_rate = api.summoner_champion_winrate(fellow_id, fellow['championId'])
            if same_team:
                predict += fellow_win_rate
            print '  Fellow player %s on %s team on champion %s having winrate %.0f%%' % (fellow_name, same_team and 'SAME' or 'ENEMY', fellow_champion_name, 100 * fellow_win_rate)

        predict_win = predict >= 2.5
        print 'prediction = %s %.2f' % (predict_win, predict)
        if win == predict_win:
            correct_predictions += 1
        total_predictions += 1
        print 'Predicted Correctly %.0f%% (%d of %d)' % (100.0 * correct_predictions / total_predictions, correct_predictions, total_predictions)
