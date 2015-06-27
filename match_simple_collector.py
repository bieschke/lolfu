#!/usr/bin/env python
"""Program that spiders the Riot API looking for matches by as many summoners
as it can discover. Two CSV lines are written to stdout for each match: One
for the victorious team and the other for the defeated.

Each CSV line has the following columns:

match_creation_timestamp (expressed in epoch seconds)
top_summoner_id
top_champion_id
jungle_summoner_id
jungle_champion_id
mid_summoner_id
mid_champion_id
adc_summoner_id
adc_champion_id
support_summoner_id
support_champion_id
victory (either "WIN" or LOSS")
"""

import riot

def main():

    api = riot.RiotAPI()

    print '''@RELATION lol_match_simple

@ATTRIBUTE match_creation NUMERIC
@ATTRIBUTE top_summoner_id NUMERIC
@ATTRIBUTE top_summoner_champion {62,24,35,19,76,143,63,33,42,201,34,23,21,53,83,101,15,92,61,41,54,78,30,126,20,48,113,104,25,150,99,102,58,114,222,429,105,38,37,39,112,69,57,412,10,120,121,2,115,134,36,43,1,84,89,157,85,107,13,98,154,80,50,432,14,67,75,4,31,77,236,106,51,122,56,26,268,68,72,17,6,32,3,74,22,161,27,110,29,86,131,11,60,12,55,245,82,96,266,119,9,91,5,64,44,90,127,18,421,8,59,267,16,45,40,111,28,79,238,254,117,103,133,7,81}
@ATTRIBUTE jungle_summoner_id NUMERIC
@ATTRIBUTE jungle_summoner_champion {62,24,35,19,76,143,63,33,42,201,34,23,21,53,83,101,15,92,61,41,54,78,30,126,20,48,113,104,25,150,99,102,58,114,222,429,105,38,37,39,112,69,57,412,10,120,121,2,115,134,36,43,1,84,89,157,85,107,13,98,154,80,50,432,14,67,75,4,31,77,236,106,51,122,56,26,268,68,72,17,6,32,3,74,22,161,27,110,29,86,131,11,60,12,55,245,82,96,266,119,9,91,5,64,44,90,127,18,421,8,59,267,16,45,40,111,28,79,238,254,117,103,133,7,81}
@ATTRIBUTE mid_summoner_id NUMERIC
@ATTRIBUTE mid_summoner_champion {62,24,35,19,76,143,63,33,42,201,34,23,21,53,83,101,15,92,61,41,54,78,30,126,20,48,113,104,25,150,99,102,58,114,222,429,105,38,37,39,112,69,57,412,10,120,121,2,115,134,36,43,1,84,89,157,85,107,13,98,154,80,50,432,14,67,75,4,31,77,236,106,51,122,56,26,268,68,72,17,6,32,3,74,22,161,27,110,29,86,131,11,60,12,55,245,82,96,266,119,9,91,5,64,44,90,127,18,421,8,59,267,16,45,40,111,28,79,238,254,117,103,133,7,81}
@ATTRIBUTE adc_summoner_id NUMERIC
@ATTRIBUTE adc_summoner_champion {62,24,35,19,76,143,63,33,42,201,34,23,21,53,83,101,15,92,61,41,54,78,30,126,20,48,113,104,25,150,99,102,58,114,222,429,105,38,37,39,112,69,57,412,10,120,121,2,115,134,36,43,1,84,89,157,85,107,13,98,154,80,50,432,14,67,75,4,31,77,236,106,51,122,56,26,268,68,72,17,6,32,3,74,22,161,27,110,29,86,131,11,60,12,55,245,82,96,266,119,9,91,5,64,44,90,127,18,421,8,59,267,16,45,40,111,28,79,238,254,117,103,133,7,81}
@ATTRIBUTE support_summoner_id NUMERIC
@ATTRIBUTE support_summoner_champion {62,24,35,19,76,143,63,33,42,201,34,23,21,53,83,101,15,92,61,41,54,78,30,126,20,48,113,104,25,150,99,102,58,114,222,429,105,38,37,39,112,69,57,412,10,120,121,2,115,134,36,43,1,84,89,157,85,107,13,98,154,80,50,432,14,67,75,4,31,77,236,106,51,122,56,26,268,68,72,17,6,32,3,74,22,161,27,110,29,86,131,11,60,12,55,245,82,96,266,119,9,91,5,64,44,90,127,18,421,8,59,267,16,45,40,111,28,79,238,254,117,103,133,7,81}
@ATTRIBUTE victory {WIN,LOSS}

@DATA'''

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
                victors = []
                defeated = []
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
                        victors.append((summoner_id, champion_id, position))
                    else:
                        defeated.append((summoner_id, champion_id, position))

                    # remember any newly discovered summoners in this match
                    if summoner_id not in known_summoner_ids:
                        known_summoner_ids.add(summoner_id)
                        remaining_summoner_ids.add(summoner_id)

                # cheesy CSV formatting
                for participants, victory in ((victors, 'WIN'), (defeated, 'LOSS')):
                    # align participants ordering with position ordering
                    output = [match['matchCreation']]
                    for participant in sorted(participants, key=lambda i: riot.POSITIONS.index(i[2])):
                        output.append(participant[0])
                        output.append(participant[1])
                    output.append(victory)
                    print ','.join([str(i) for i in output])

if __name__ == '__main__':
    main()
