lolfu
=====
Smattering of Python programs and utilities written around Riot's League of Legends API.

The <code>riot.py</code> module is a simple wrapper around Riot's LOL API. You can
either pass your api key directly to it's constructor, or create a <code>riot.cfg</code>
file that it'll read from upon instantiation.

The <code>dodge.py</code> utility is a simple command line program that someday will
advise a player (a) whether or not they should dodge their current game based upon
data available in champion select, and (b) which champion, lane, and role is optimal
for them to choose based on their match history and compositional aspects.

The <code>get_matches.py</code> program walks a starting set of summoners, retrieves
complete match history for each of those summoners, and then continues to spider
the observed summoners from those matches, outputting CSV data to stdout for all of
the retrieved matches.

<i>lolfu isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing League of Legends. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc. League of Legends © Riot Games, Inc.</i>
l
