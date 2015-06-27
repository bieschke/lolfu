#!/usr/bin/env python
"""Program that spiders the Riot API looking for matches by as many summoners
as it can discover. One ARFF data line is written to stdout for each match.

Each ARFF data line has the following columns:

match_id
match_timestamp (expressed in epoch seconds)
winner_top_summoner_id
winner_top_champion_id
winner_jungle_summoner_id
winner_jungle_champion_id
winner_mid_summoner_id
winner_mid_champion_id
winner_adc_summoner_id
winner_adc_champion_id
winner_support_summoner_id
winner_support_champion_id
loser_top_summoner_id
loser_top_champion_id
loser_jungle_summoner_id
loser_jungle_champion_id
loser_mid_summoner_id
loser_mid_champion_id
loser_adc_summoner_id
loser_adc_champion_id
loser_support_summoner_id
loser_support_champion_id
"""

import riot

def main():

    api = riot.RiotAPI()

    print '''@RELATION lol_match_simple

@ATTRIBUTE match_id NUMERIC
@ATTRIBUTE match_timestamp NUMERIC
@ATTRIBUTE winner_top_summoner_id NUMERIC
@ATTRIBUTE winner_top_summoner_champion_id %s
@ATTRIBUTE winner_jungle_summoner_id NUMERIC
@ATTRIBUTE winner_jungle_summoner_champion_id %s
@ATTRIBUTE winner_mid_summoner_id NUMERIC
@ATTRIBUTE winner_mid_summoner_champion_id %s
@ATTRIBUTE winner_adc_summoner_id NUMERIC
@ATTRIBUTE winner_adc_summoner_champion_id %s
@ATTRIBUTE winner_support_summoner_id NUMERIC
@ATTRIBUTE winner_support_summoner_champion_id %s
@ATTRIBUTE loser_top_summoner_id NUMERIC
@ATTRIBUTE loser_top_summoner_champion_id %s
@ATTRIBUTE loser_jungle_summoner_id NUMERIC
@ATTRIBUTE loser_jungle_summoner_champion_id %s
@ATTRIBUTE loser_mid_summoner_id NUMERIC
@ATTRIBUTE loser_mid_summoner_champion_id %s
@ATTRIBUTE loser_adc_summoner_id NUMERIC
@ATTRIBUTE loser_adc_summoner_champion_id %s
@ATTRIBUTE loser_support_summoner_id NUMERIC
@ATTRIBUTE loser_support_summoner_champion_id %s

@DATA''' % tuple([riot.RIOT_CHAMPION_IDS]*10)

    known_summoner_ids = api.bootstrap_summoner_ids.copy()
    remaining_summoner_ids = known_summoner_ids.copy()
    known_match_ids = set()

    while remaining_summoner_ids:
        summoner_id = remaining_summoner_ids.pop()

        begin_index = 0
        while True:
            # walk through summoner's match history 15 matches at a time
            # 15 is the most number of matches the Riot API allows you to retrieve at one time
            step = 15
            end_index = begin_index + step
            matches = api.matchhistory(summoner_id, begin_index, end_index).get('matches', [])
            if not matches:
                break
            begin_index += step

            for match in matches:
                match_id = match['matchId']
                if match_id in known_match_ids:
                    continue
                known_match_ids.add(match_id)

                # the matchhistory endpoint does not include information in all
                # participants within the match, to receive those we issue a second
                # call to the match endpoint.
                match = api.match(match_id)

                # create a mapping of participant ids to summoner ids
                summoner_ids = {}
                for identity in match['participantIdentities']:
                    participant_id = identity['participantId']
                    summoner_id = identity['player']['summonerId']
                    summoner_ids[participant_id] = summoner_id

                # collect data for each participant
                winners = []
                losers = []
                for participant in match['participants']:
                    summoner_id = summoner_ids[participant['participantId']]
                    champion_id = participant['championId']
                    stats = participant['stats']
                    timeline = participant['timeline']
                    lane = timeline['lane']
                    role = timeline['role']
                    position = riot.position(lane, role)
                    victory = stats['winner']
                    if victory:
                        winners.append((summoner_id, champion_id, position))
                    else:
                        losers.append((summoner_id, champion_id, position))

                    # remember any newly discovered summoners in this match
                    if summoner_id not in known_summoner_ids:
                        known_summoner_ids.add(summoner_id)
                        remaining_summoner_ids.add(summoner_id)

                # cheesy CSV formatting
                output = [match_id, match['matchCreation']]
                for participants in (winners, losers):
                    # align participants ordering with position ordering
                    for participant in sorted(participants, key=lambda i: riot.POSITIONS.index(i[2])):
                        output.append(participant[0])
                        output.append(participant[1])
                print ','.join([str(i) for i in output])

if __name__ == '__main__':
    main()
