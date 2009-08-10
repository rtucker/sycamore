# A Twitter plugin for Sycamore.

# Ryan Tucker <rtucker@gmail.com>

Dependencies = ["time"]

import simplejson
import time
import urllib

from Sycamore import config
from Sycamore import wikiutil

SOCKET_TIMEOUT = 5 # break fast if twitter is broken

# from http://snipplr.com/view.php?codeview&id=5713
def elapsed_time(seconds, suffixes=['year','week','day','hour','minute','second'], add_s=True, separator=' '):
    """
    Takes an amount of seconds and turns it into a human-readable amount of time.
    """
    # the formatted time string to be returned
    time = []
    
    # the pieces of time to iterate over (days, hours, minutes, etc)
    # - the first piece in each tuple is the suffix (d, h, w)
    # - the second piece is the length in seconds (a day is 60s * 60m * 24h)
    parts = [(suffixes[0], 60 * 60 * 24 * 7 * 52),
          (suffixes[1], 60 * 60 * 24 * 7),
          (suffixes[2], 60 * 60 * 24),
          (suffixes[3], 60 * 60),
          (suffixes[4], 60),
          (suffixes[5], 1)]
    
    # for each time piece, grab the value and remaining seconds, and add it to
    # the time string
    for suffix, length in parts:
        value = seconds / length
        if value > 0 and len(time) < 2:
            seconds = seconds % length
            time.append('%s %s' % (str(value),
                           (suffix, (suffix, suffix + 's')[value > 1])[add_s]))
        if seconds < 1:
            break
    
    return separator.join(time)

def execute(macro, args, formatter=None, test=None):
    if not formatter:
        formatter = macro.formatter

    # Require memcache
    if config.memcache:
        mc = macro.request.mc
    else:
        return formatter.rawHTML('<!-- Twitter macro requires memcache for performance reasons -->')

    if args:
        tokens = args.split(',')
        query = ' OR '.join('"%s"' % p.strip() for p in tokens)
        nicequery = ' or '.join("''%s''" % p.strip() for p in tokens)
        isdefault = False
    else:
        # If no query is specified, default to the domain part of our domain
        # name (e.g. turbowiki.org -> turbowiki) and attach usage message
        query = config.wiki_base_domain.split('.')[0]
        nicequery = query
        isdefault = True

    # get the info from search.twitter.com
    class AppURLopener(urllib.FancyURLopener):
        version = "SycamoreTwitterMacro/1.8 (http://github.org/rtucker/sycamore/)"

    urllib._urlopener = AppURLopener()

    quotedquery = urllib.quote_plus(query + ' ' + config.twitter_params)

    fromcache = 'yes'
    response_dict = mc.get("twitter-18-" + urllib.quote(query))
    if not response_dict:
        fromcache = 'no'
        response_dict = simplejson.loads(urllib.urlopen('http://search.twitter.com/search.json?q=%s&rpp=%i' % (quotedquery, config.twitter_maxlines)).read())
        mc.set("twitter-18-" + urllib.quote(query), response_dict, time=3600)

    display_list = ["||<bgcolor='#E0E0FF'>'''Local Twitter search results for [http://search.twitter.com/search?q=%s %s]'''||" % (quotedquery, nicequery)]

    outputting = False

    if len(response_dict['results']) > 0:
        for i in response_dict['results']:
            name = i['from_user']
            text = wikiutil.simpleStrip(macro.request, i['text']).replace('&amp;','&').replace('\n',' ')
            try:
                location = i['location']
            except KeyError:
                location = ''
            created = time.mktime(time.strptime(i['created_at'], '%a, %d %b %Y %H:%M:%S +0000'))
            created_seconds_ago = int(time.mktime(time.gmtime()) - created)
            id = i['id']
            link = 'http://twitter.com/%s/statuses/%i' % (name, id)
            namelink = 'http://twitter.com/%s' % name
            if created_seconds_ago < config.twitter_maxtime:
                display_list.append('||%s ^[%s %s], %s, [%s %s ago]^||' % (text, namelink, name, location, link, elapsed_time(created_seconds_ago,separator=', ')))
                outputting = True

    if not outputting:
        display_list.append('||Nothing on [http://twitter.com/ Twitter] in the local area... maybe you should go stir something up.||')

    if isdefault:
        display_list.append("||''The Twitter macro searches Twitter for recent local traffic about a topic!  Usage: {{{[[Twitter(search string)]]}}}''||")

    outstring = '\n'.join(p for p in display_list)

    return wikiutil.wikifyString(outstring, macro.request, formatter.page, strong=True)

