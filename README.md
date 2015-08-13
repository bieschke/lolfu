lolfu
=====
Web application written around Riot's League of Legends API that allows summoners to
look up how they perform on different champion position combinations.

Dependencies:
<li>Python 3.4.3 - https://www.python.org</li>
<li>Requests 2.7.0 - http://requests.readthedocs.org</li>
<li>CherryPy 3.8.0 - http://www.cherrypy.org</li>
<li>Mako 1.0.1 - http://www.makotemplates.org</li>
<li>aiohttp 0.16.6 - https://aiohttp.readthedocs.org</li>
<li>cachetools 1.0.3 - http://pythonhosted.org/cachetools/</li>

<code>site.py</code> is a CherryPy application that allows one to lookup summoners and see
what is the winrate optimal champions they should be playing in each role.

<code>riot.py</code> is a simple wrapper around Riot's LOL API. This wrapper is resilient
to temporary downtime on Riot's server, using a progressively delayed retry mechanism when 
encountering these types of server failures. When surpassing Riot API rate limits, the 
wrapper will automatically respect the Retry-After header and resume querying after the 
rate limit threshold has passed.

<i>lolfu isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing League of Legends. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc. League of Legends © Riot Games, Inc.</i>
