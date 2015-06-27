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
                    # TODO add more than just position & champ
                    # use all general summoner and champ stats
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
                    participants.sort(key=lambda i: riot.POSITIONS.index(i[2]))
                    p = ''
                    for participant in participants:
                        position_format = (
                            ('summoner_id', participant[0]),
                            ('champion_id', participant[1]),
                            )
                        p += ',' + ','.join([str(i[1]) for i in position_format])
                    print '%s%s,%s' % (match['matchCreation'], p, victory)

if __name__ == '__main__':
    main()
