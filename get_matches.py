#!/usr/bin/env python
"""Program that spiders the Riot API looking for matches by as many summoners
as it can discover. A single line is written to stdout for each match-summoner
pair with hopefully useful data pertaining to that combination. This means a
single match is represented as 10 lines of output. Each line of output is
formatted as CSV.
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
                # output a line of data for each participant in this match
                for participant in match['participants']:
                    summoner_id = summoner_ids[participant['participantId']]
                    stats = participant['stats']
                    timeline = participant['timeline']
                    output_format = (
                        ('match_id', match_id),
                        ('summoner_id', summoner_id),
                        ('champion_id', participant['championId']),
                        ('tier', participant['highestAchievedSeasonTier']),
                        ('lane', timeline['lane']),
                        ('role', timeline['role']),
                        ('kills', stats['kills']),
                        ('deaths', stats['deaths']),
                        ('assists', stats['assists']),
                        ('gold_earned', stats['goldEarned']),
                        ('gold_spent', stats['goldSpent']),
                        ('dmg', stats['totalDamageDealt']),
                        ('dmg_champs', stats['totalDamageDealtToChampions']),
                        ('dmg_taken', stats['totalDamageTaken']),
                        ('dmg_healed', stats['totalHeal']),
                        ('cc', stats['totalTimeCrowdControlDealt']),
                        ('wards_placed', stats['wardsPlaced']),
                        ('wards_killed', stats['wardsKilled']),
                        ('winner', stats['winner']),
                        )
                    # cheesy CSV formatting
                    print ','.join([str(i[1]) for i in output_format])
                    # remember any newly discovered summoners in this match
                    if summoner_id not in known_summoner_ids:
                        known_summoner_ids.add(summoner_id)
                        remaining_summoner_ids.add(summoner_id)

if __name__ == '__main__':
    main()
