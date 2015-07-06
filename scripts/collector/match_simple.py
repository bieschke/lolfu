#!/usr/bin/env python3.4
"""Program that spiders the Riot API looking for matches by as many summoners
as it can discover. One ARFF data line is written to stdout for each match.
This program also accepts optional command line arguments, where each argument
is a previously collected ARFF file. Supplying the previously created data
files allows this program to skip existing matches and only output data for
previously unobserved matches.
"""

import fileinput
import requests
import riot
import sys


def main():

    api = riot.RiotAPI()

    print('''@RELATION lol_match_simple

@ATTRIBUTE match_id NUMERIC
@ATTRIBUTE match_version STRING
@ATTRIBUTE match_timestamp NUMERIC
@ATTRIBUTE winner_top_summoner_id NUMERIC
@ATTRIBUTE winner_top_champion_id %s
@ATTRIBUTE winner_top_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE winner_jungle_summoner_id NUMERIC
@ATTRIBUTE winner_jungle_champion_id %s
@ATTRIBUTE winner_jungle_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE winner_mid_summoner_id NUMERIC
@ATTRIBUTE winner_mid_champion_id %s
@ATTRIBUTE winner_mid_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE winner_adc_summoner_id NUMERIC
@ATTRIBUTE winner_adc_champion_id %s
@ATTRIBUTE winner_adc_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE winner_support_summoner_id NUMERIC
@ATTRIBUTE winner_support_champion_id %s
@ATTRIBUTE winner_support_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE loser_top_summoner_id NUMERIC
@ATTRIBUTE loser_top_champion_id %s
@ATTRIBUTE loser_top_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE loser_jungle_summoner_id NUMERIC
@ATTRIBUTE loser_jungle_champion_id %s
@ATTRIBUTE loser_jungle_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE loser_mid_summoner_id NUMERIC
@ATTRIBUTE loser_mid_champion_id %s
@ATTRIBUTE loser_mid_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE loser_adc_summoner_id NUMERIC
@ATTRIBUTE loser_adc_champion_id %s
@ATTRIBUTE loser_adc_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}
@ATTRIBUTE loser_support_summoner_id NUMERIC
@ATTRIBUTE loser_support_champion_id %s
@ATTRIBUTE loser_support_tier {Challenger,Master,Diamond,Platinum,Gold,Silver,Bronze}

@DATA''' % tuple([riot.RIOT_CHAMPION_IDS]*10))

    # start by bootstrapping summoner ids
    known_summoner_ids = api.bootstrap_summoner_ids.copy()
    remaining_summoner_ids = known_summoner_ids.copy()
    known_match_ids = set()

    # Optional command line arguments for this program are the names of all previously
    # collected data files. Accumulate all of the match ids for which we have already
    # collected data.
    if sys.argv[1:]:
        for line in fileinput.input():
            try:
                # rely on the first column being the match id
                known_match_ids.add(int(line.split(',')[0]))
            except ValueError:
                pass # ignore any lines that don't start with a number
        print('%d preexisting matches found' % len(known_match_ids), file=sys.stderr)

    while remaining_summoner_ids:
        summoner_id = remaining_summoner_ids.pop()

        abort = False
        begin_index = 0
        step = 15 # maximum allowable through Riot API
        while not abort:
            abort = False
            # walk through summoner's match history STEP matches at a time
            end_index = begin_index + step
            matches = api.matchhistory(summoner_id, begin_index, end_index).get('matches', [])
            if not matches:
                break
            begin_index += step

            for match in matches:
                match_id = match['matchId']
                match_version = match['matchVersion']
                if match_id in known_match_ids:
                    continue
                if not match_version.startswith(riot.CURRENT_VERSION):
                    abort = True
                    break
                known_match_ids.add(match_id)

                # the matchhistory endpoint does not include information in all
                # participants within the match, to receive those we issue a second
                # call to the match endpoint.
                try:
                    match = api.match(match_id)
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404:
                        continue # skip matches that no longer exist
                    raise

                # create a mapping of participant ids to summoner ids
                summoner_ids = {}
                for identity in match['participantIdentities']:
                    participant_id = identity['participantId']
                    summoner_id = identity['player']['summonerId']
                    summoner_ids[participant_id] = summoner_id

                # create a mapping of summoner ids to tier and divisions
                tier_divisions = api.tiers_divisions(summoner_ids.values())

                # collect data for each participant
                winners = {}
                losers = {}
                for participant in match['participants']:
                    participant_id = participant['participantId']
                    summoner_id = summoner_ids[participant_id]
                    champion_id = participant['championId']
                    stats = participant['stats']
                    timeline = participant['timeline']
                    lane = timeline['lane']
                    role = timeline['role']
                    tier = tier_divisions.get(summoner_id, ['?', '?'])[0]
                    position = riot.position(lane, role, champion_id)
                    if stats['winner']:
                        winners[position] = (summoner_id, champion_id, tier)
                    else:
                        losers[position] = (summoner_id, champion_id, tier)

                    # remember any newly discovered summoners in this match
                    if summoner_id not in known_summoner_ids:
                        known_summoner_ids.add(summoner_id)
                        remaining_summoner_ids.add(summoner_id)

                # cheesy CSV formatting
                output = [match_id, match_version, match['matchCreation']]
                for participants in (winners, losers):
                    # align participants ordering with position ordering
                    for position in riot.POSITIONS:
                        output.extend(participants.get(position, ['?', '?', '?']))
                print(','.join([str(i) for i in output]))


if __name__ == '__main__':
    main()
