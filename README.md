lolfu
=====
Smattering of Python programs and utilities written around Riot's League of Legends API.

<code>riot.py</code> is a simple wrapper around Riot's LOL API. You can either pass your 
api key directly to it's constructor, or create a <code>riot.cfg</code> file that it'll 
read from upon instantiation. This wrapper is resilient to temporary downtime on Riot's 
server, using a progressively delayed retry mechanism when encountering these types of 
server failures. When surpassing Riot API rate limits, the wrapper will automatically 
respect the Retry-After header and resume querying after the rate limit threshold has 
passed.

<code>match_simple_collector.py</code> walks a starting set of summoners, retrieves
complete match history for each of those summoners, and then continues to spider the 
observed summoners from those matches, outputting ARFF data to stdout for all of the
retrieved matches.

<code>match_complex_converter.py</code> converts a simple match ARFF file into a 
complex match ARFF file by layering in summoner and summoner-champion statistics in 
addition to the bare bones statistics provided in a simple match.

<code>match_predictor.py</code> is a simple command line program that predicts the
likelihood of winning the described match.

<code>arff_reader.py</code> is a command line utility that reads in ARFF via stdin and
writes either CSV or JSON-ified dictionaries to stdout. Keys in the JSON output are 
the ARFF attribute names and values are the ARFF data. Useful for piping ARFF files.

<i>lolfu isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing League of Legends. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc. League of Legends © Riot Games, Inc.</i>
